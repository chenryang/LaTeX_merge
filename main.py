#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import argparse
import glob
import shutil

def remove_comments(content):
    """Removes LaTeX comments (% lines, comment environment, \\iffalse)."""
    # Remove single-line comments (%), handling escaped %
    content = re.sub(r'(?<!\\)%.*?$', '', content, flags=re.MULTILINE)
    # Remove comment environment
    content = re.sub(r'\\begin\s*\{\s*comment\s*\}.*?\\end\s*\{\s*comment\s*\}', '',
                     content, flags=re.DOTALL)
    # Remove \iffalse ... \fi blocks
    content = re.sub(r'\\iffalse.*?\\fi', '', content, flags=re.DOTALL)
    return content

def remove_excessive_blank_lines(content):
    """Reduces sequences of 3 or more blank lines to exactly 2 blank lines."""
    # A blank line is defined as a line containing only whitespace (spaces, tabs)
    # Pattern matches:
    # \n         - a newline
    # ([ \t]*\n) - a line containing only spaces/tabs followed by a newline
    # {2,}       - the previous group repeated 2 or more times
    # This effectively matches 3 or more consecutive newlines, potentially separated by whitespace-only lines.
    # Replace with exactly two newlines.
    content = re.sub(r'\n([ \t]*\n){2,}', '\n\n', content)
    return content

def find_used_pdfs(content):
    """Finds PDF files referenced in the LaTeX content."""
    used_pdfs = set()

    # Common commands that include graphics/PDFs
    patterns = [
        r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}',
        r'\\includepdf(?:\[.*?\])?\{([^}]+)\}',
        r'\\pdfximage\{([^}]+)\}',
        # Less common, but sometimes filenames appear in captions directly
        r'\\caption\{.*?([a-zA-Z0-9_\-]+\.pdf).*?\}',
    ]

    for pattern in patterns:
        # Use re.IGNORECASE for flexibility, though filenames are often case-sensitive on Linux
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            filename = match.group(1).strip()

            # Handle cases where extension might be omitted (common for includegraphics)
            # Assume .pdf if no extension is given
            if not filename.lower().endswith('.pdf'):
                # Check if there's *any* extension or just a base name
                base, ext = os.path.splitext(os.path.basename(filename))
                if not ext: # No extension found
                    filename += '.pdf'
                else:
                    # It has an extension, but not .pdf, skip? Or maybe user *did* include e.g. .png?
                    # For this script focused on PDFs, we'll only add .pdf if *no* extension exists.
                    # If the user specified another extension, we assume they meant that.
                    pass # Keep the original filename with its non-pdf extension

            # Only proceed if we now think it's a PDF file
            if filename.lower().endswith('.pdf'):
                # Check common locations relative to the current content scope
                # Note: This check happens *after* expansion, so paths are relative to the original main file's dir
                # or potentially complex if \input uses relative paths itself.
                # For simplicity, we check existence directly and then common subdirs.
                
                # Try direct path first (might be absolute or relative to main file's dir)
                if os.path.exists(filename):
                    used_pdfs.add(os.path.abspath(filename))
                    continue # Found it

                # Try common graphics directories relative to the base directory
                # (Assuming base_dir is passed or accessible, currently it's not directly here)
                # For now, let's assume paths are relative to the script's execution dir or main file dir
                # This part might need refinement depending on project structure complexity
                possible_dirs = ['.', 'figures', 'images', 'img', 'graphics']
                found = False
                for directory in possible_dirs:
                    path_to_check = os.path.join(directory, filename)
                    if os.path.exists(path_to_check):
                        used_pdfs.add(os.path.abspath(path_to_check))
                        found = True
                        break
                # if not found:
                #     print(f"Warning: Referenced PDF '{filename}' not found in common locations.", file=sys.stderr)

    return used_pdfs


def expand_input_commands(content, base_dir):
    """Recursively replaces \\input and \\include commands with file content."""
    # Pattern to find \input{file} or \include{file}
    input_pattern = re.compile(r'\\(?:input|include)\s*\{\s*([^}]+)\s*\}')

    # Use finditer to handle multiple occurrences and potential recursion safely
    processed_content = ""
    last_end = 0

    for match in input_pattern.finditer(content):
        # Append content before the match
        processed_content += content[last_end:match.start()]

        filename = match.group(1).strip()
        # Add .tex extension if missing
        if not os.path.splitext(filename)[1]:
            filename += '.tex'

        # Construct the full path relative to the *current* file's directory
        filepath = os.path.join(base_dir, filename)
        filepath = os.path.abspath(filepath) # Normalize path

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # --- Processing within the included file ---
            # 1. Remove comments from the included file *first*
            file_content = remove_comments(file_content)

            # 2. Recursively expand inputs within this file
            #    The base directory for nested inputs is the directory of the *included* file
            included_base_dir = os.path.dirname(filepath)
            expanded_file_content = expand_input_commands(file_content, included_base_dir)

            # Append the processed content of the included file
            processed_content += expanded_file_content

        except FileNotFoundError:
            print(f"Warning: File '{filepath}' not found. Skipping inclusion.", file=sys.stderr)
            # Keep the original \input command in the output? Or just skip? Skipping for now.
            # To keep: processed_content += match.group(0)

        except Exception as e:
            print(f"Error processing file '{filepath}': {e}", file=sys.stderr)
            # Keep the original command on error?
            # processed_content += match.group(0)


        last_end = match.end()

    # Append any remaining content after the last match
    processed_content += content[last_end:]

    return processed_content


def find_all_pdfs_in_project():
    """Finds all PDF files recursively from the current directory downwards."""
    all_pdfs = set()
    # Consider searching from the script's execution directory or a specified root
    # For simplicity, using current directory as root for glob
    for pdf_file in glob.glob('**/*.pdf', recursive=True):
        all_pdfs.add(os.path.abspath(pdf_file))
    return all_pdfs

def delete_unused_files(output_file_abs_path, used_pdfs, delete_tex=False, delete_unused_pdf=False):
    """Deletes unused .tex and .pdf files based on flags."""
    project_root = os.path.dirname(output_file_abs_path) # A reasonable guess for the project root

    # --- Delete unused TeX files ---
    if delete_tex:
        print("\nDeleting unused .tex files...")
        # Search recursively from the project root
        tex_files = glob.glob(os.path.join(project_root, '**/*.tex'), recursive=True)
        deleted_count = 0
        kept_count = 0
        for tex_file in tex_files:
            tex_abs_path = os.path.abspath(tex_file)
            # Do not delete the generated output file
            if tex_abs_path != output_file_abs_path:
                try:
                    os.remove(tex_abs_path)
                    print(f"  Deleted: {os.path.relpath(tex_abs_path, project_root)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  Cannot delete {os.path.relpath(tex_abs_path, project_root)}: {e}", file=sys.stderr)
            else:
                kept_count += 1
        print(f"TeX files: {deleted_count} deleted, {kept_count} kept (output file).")


    # --- Delete unused PDF files ---
    if delete_unused_pdf:
        print("\nDeleting unused PDF files...")
        all_project_pdfs = find_all_pdfs_in_project()
        # Ensure comparison uses absolute paths
        unused_pdfs = all_project_pdfs - used_pdfs

        deleted_count = 0
        kept_count = len(used_pdfs)

        if not unused_pdfs:
             print("  No unused PDF files found to delete.")
        else:
            for pdf_file_abs in unused_pdfs:
                 # Basic safety check: avoid deleting outside the project root?
                 # if not pdf_file_abs.startswith(project_root):
                 #    print(f"  Skipping potentially external PDF: {pdf_file_abs}", file=sys.stderr)
                 #    continue
                try:
                    os.remove(pdf_file_abs)
                    print(f"  Deleted unused PDF: {os.path.relpath(pdf_file_abs, project_root)}")
                    deleted_count +=1
                except Exception as e:
                    print(f"  Cannot delete {os.path.relpath(pdf_file_abs, project_root)}: {e}", file=sys.stderr)
            print(f"PDF files: {deleted_count} deleted, {kept_count} kept (used).")


def main():
    parser = argparse.ArgumentParser(
        description='Expand LaTeX \\input/\\include, remove comments & excessive blank lines, optionally delete source/unused files.',
        formatter_class=argparse.RawTextHelpFormatter # Nicer help formatting
        )
    parser.add_argument('input_file', help='Main input LaTeX file (e.g., main.tex)')
    parser.add_argument('output_file', help='Output file for the combined LaTeX content (e.g., combined.tex)')
    parser.add_argument('--delete-tex', action='store_true',
                        help='Delete all other .tex files in the project directory\n'
                             'after successful expansion (except the output file).\n'
                             'USE WITH CAUTION!')
    parser.add_argument('--delete-unused-pdf', action='store_true',
                        help='Delete all .pdf files found recursively in the project directory\n'
                             'that are NOT referenced via \\includegraphics, \\includepdf etc.\n'
                             'in the expanded content. USE WITH CAUTION!')
    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output_file
    output_file_abs_path = os.path.abspath(output_file)

    if not os.path.exists(input_file):
         print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
         sys.exit(1)

    if os.path.abspath(input_file) == output_file_abs_path:
         print(f"Error: Input file and output file cannot be the same ('{input_file}').", file=sys.stderr)
         sys.exit(1)

    try:
        print(f"Reading main file: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Determine the base directory for resolving relative paths in \input commands
        base_dir = os.path.dirname(os.path.abspath(input_file))
        if not base_dir: # If input file is in current dir
            base_dir = '.'

        print("Processing...")
        # Step 1: Remove comments from the main file first
        content = remove_comments(content)

        # Step 2: Recursively expand \input and \include commands
        #         (comments within included files are removed during expansion)
        print("  Expanding \\input/\\include commands...")
        content = expand_input_commands(content, base_dir)

        # Step 3: Remove excessive blank lines from the fully expanded content
        print("  Removing excessive blank lines...")
        content = remove_excessive_blank_lines(content)

        # Step 4 (Preparation for optional deletion): Find all used PDFs *after* expansion
        print("  Identifying used PDF files...")
        used_pdfs = find_used_pdfs(content)
        print(f"  Found {len(used_pdfs)} unique PDF files referenced.")
        # for pdf in sorted(list(used_pdfs)):
        #     print(f"    - {os.path.relpath(pdf, base_dir)}")


        # Step 5: Write the processed content to the output file
        print(f"\nWriting expanded content to: {output_file}")
        os.makedirs(os.path.dirname(output_file_abs_path), exist_ok=True) # Ensure output directory exists
        with open(output_file_abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("Success: Content written.")

        # Step 6: Perform optional deletions
        delete_unused_files(output_file_abs_path, used_pdfs,
                            args.delete_tex,
                            args.delete_unused_pdf)

        print("\nProcessing completed.")
        if not args.delete_tex and not args.delete_unused_pdf:
            print("No files were deleted (use --delete-tex or --delete-unused-pdf to enable deletion).")

    except Exception as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
        sys.exit(1)

if __name__ == "__main__":
    main()
