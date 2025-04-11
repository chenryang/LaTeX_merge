#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import argparse
import glob
import shutil

def remove_comments(content):
    content = re.sub(r'(?<!\\)%.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'\\begin\s*\{\s*comment\s*\}.*?\\end\s*\{\s*comment\s*\}', '', 
                     content, flags=re.DOTALL)
    content = re.sub(r'\\iffalse.*?\\fi', '', content, flags=re.DOTALL)
    return content

def find_used_pdfs(content):
    used_pdfs = set()
    
    patterns = [
        r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}',
        r'\\includepdf(?:\[.*?\])?\{([^}]+)\}',
        r'\\pdfximage\{([^}]+)\}',
        r'\\caption\{.*?([a-zA-Z0-9_\-]+\.pdf).*?\}',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            filename = match.group(1).strip()
            
            if not filename.lower().endswith('.pdf'):
                if '.' not in os.path.basename(filename):
                    filename += '.pdf'
            
            if os.path.exists(filename):
                used_pdfs.add(os.path.abspath(filename))
            else:
                possible_paths = [
                    filename,
                    os.path.join('figures', filename),
                    os.path.join('images', filename),
                    os.path.join('img', filename),
                    os.path.join('graphics', filename),
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        used_pdfs.add(os.path.abspath(path))
                        break
    
    return used_pdfs

def expand_input_commands(content, base_dir):
    input_pattern = re.compile(r'\\(?:input|include)\s*\{\s*([^}]+)\s*\}')
    
    matches = list(input_pattern.finditer(content))
    
    for match in reversed(matches):
        filename = match.group(1)
        
        if not os.path.splitext(filename)[1]:
            filename += '.tex'
        
        filepath = os.path.join(base_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            file_content = remove_comments(file_content)
            included_base_dir = os.path.dirname(filepath)
            file_content = expand_input_commands(file_content, included_base_dir)
            
            content = content[:match.start()] + file_content + content[match.end():]
            
        except FileNotFoundError:
            print(f"Warning: File '{filepath}' not found", file=sys.stderr)
    
    return content

def delete_unused_pdfs(content, delete_unused_pdf=False):
    if not delete_unused_pdf:
        return
    
    used_pdfs = find_used_pdfs(content)
    
    all_pdfs = set()
    for pdf_file in glob.glob('**/*.pdf', recursive=True):
        all_pdfs.add(os.path.abspath(pdf_file))
    
    unused_pdfs = all_pdfs - used_pdfs
    
    for pdf_file in unused_pdfs:
        try:
            os.remove(pdf_file)
            print(f"Deleted unused PDF: {pdf_file}")
        except Exception as e:
            print(f"Cannot delete {pdf_file}: {e}", file=sys.stderr)

def delete_files(output_file, content, delete_tex=False, delete_unused_pdf=False):
    output_abs_path = os.path.abspath(output_file)
    
    if delete_tex:
        tex_files = glob.glob('**/*.tex', recursive=True)
        
        for tex_file in tex_files:
            tex_abs_path = os.path.abspath(tex_file)
            if tex_abs_path != output_abs_path:
                try:
                    os.remove(tex_abs_path)
                    print(f"Deleted: {tex_file}")
                except Exception as e:
                    print(f"Cannot delete {tex_file}: {e}", file=sys.stderr)
    
    if delete_unused_pdf:
        delete_unused_pdfs(content, delete_unused_pdf)

def main():
    parser = argparse.ArgumentParser(description='Recursively expand LaTeX files, remove comments, and delete temporary files')
    parser.add_argument('input_file', help='Input LaTeX file')
    parser.add_argument('output_file', help='Output expanded LaTeX file')
    parser.add_argument('--delete-tex', action='store_true', help='Delete other .tex files (keep by default)')
    parser.add_argument('--delete-unused-pdf', action='store_true', help='Delete unused PDF files (keep all by default)')
    args = parser.parse_args()
    
    input_file = args.input_file
    output_file = args.output_file
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        base_dir = os.path.dirname(os.path.abspath(input_file))
        if not base_dir:
            base_dir = '.'
        
        content = remove_comments(content)
        content = expand_input_commands(content, base_dir)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Success: '{input_file}' has been expanded and saved to '{output_file}'")
        
        delete_files(output_file, content, 
                     args.delete_tex, 
                     args.delete_unused_pdf)
        
        print("Processing completed.")
        if args.delete_tex:
            print("All .tex files except the output file have been deleted")
        if args.delete_unused_pdf:
            print("All unused PDF files have been deleted")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
