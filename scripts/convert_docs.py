import os
import re
import base64
import urllib.request
import hashlib
import subprocess

def strip_emojis(text):
    # Match emoji ranges and variation selectors to ensure LaTeX compilation doesn't fail
    emoji_pattern = re.compile(
        r'[\U0001f300-\U0001f5ff'
        r'\U0001f600-\U0001f64f'
        r'\U0001f680-\U0001f6ff'
        r'\U0001f900-\U0001f9ff'
        r'\U0001fa70-\U0001faff'
        r'\u2600-\u26ff'
        r'\u2700-\u27bf'
        r'\uFE0F]+',
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)

def process_mermaid_blocks(content, images_dir):
    # Regex to find mermaid code blocks
    pattern = re.compile(r'```mermaid\s*\n(.*?)\n```', re.DOTALL)
    
    index = 0
    def replace_mermaid(match):
        nonlocal index
        index += 1
        code = match.group(1).strip()
        
        # Create a unique hash for the mermaid code
        code_hash = hashlib.md5(code.encode('utf-8')).hexdigest()
        img_filename = f"mermaid_{code_hash}.png"
        img_path = os.path.join(images_dir, img_filename)
        rel_img_path = f"docs/images/{img_filename}"
        
        # Download image from mermaid.ink if it doesn't already exist
        if not os.path.exists(img_path):
            print(f"Rendering Mermaid diagram {index}...")
            # Base64 encode the code
            b64_code = base64.urlsafe_b64encode(code.encode('utf-8')).decode('ascii')
            url = f"https://mermaid.ink/img/{b64_code}"
            
            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    image_data = response.read()
                with open(img_path, 'wb') as img_file:
                    img_file.write(image_data)
                print(f"Saved: {img_path}")
            except Exception as e:
                print(f"Warning: Failed to download Mermaid diagram from {url}: {e}")
                # Fallback: keep the original markdown code block
                return match.group(0)
        
        # Replace with markdown image syntax
        return f"![Sơ đồ minh họa {index}]({rel_img_path})"
        
    return pattern.sub(replace_mermaid, content)

def convert_md_file(md_path, chapters_dir, images_dir):
    filename = os.path.basename(md_path)
    base_name, _ = os.path.splitext(filename)
    tex_path = os.path.join(chapters_dir, f"{base_name}.tex")
    
    print(f"Processing: {filename}")
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. Process Mermaid blocks first
    content = process_mermaid_blocks(content, images_dir)
    
    # 2. Strip emojis (LaTeX hates them)
    content = strip_emojis(content)
    
    # 3. Replace GitHub alerts with LaTeX/Markdown friendly bold text
    content = content.replace('> [!NOTE]', '> **Ghi chú:**')
    content = content.replace('> [!IMPORTANT]', '> **Quan trọng:**')
    content = content.replace('> [!WARNING]', '> **Cảnh báo:**')
    content = content.replace('> [!TIP]', '> **Mẹo:**')
    content = content.replace('> [!CAUTION]', '> **Thận trọng:**')
    
    # 4. Clean up relative markdown links (convert [text](./path.md) to **text**)
    content = re.sub(r'\[([^\]]+)\]\(\./[^)]+\.md\)', r'**\1**', content)
    
    # 4.5 Clean up subscripts for chemical and air quality formulas to LaTeX math mode
    content = content.replace('CO₂', 'CO$_2$')
    content = content.replace('CO2', 'CO$_2$')
    content = content.replace('PM₂.₅', 'PM$_{2.5}$')
    content = content.replace('PM2.5', 'PM$_{2.5}$')
    content = content.replace('PM₁₀', 'PM$_{10}$')
    content = content.replace('PM10', 'PM$_{10}$')
    content = content.replace('NOx', 'NO$_x$')
    
    # Write to a temporary file
    temp_md_path = os.path.join(chapters_dir, f"temp_{base_name}.md")
    with open(temp_md_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    # 5. Call pandoc to convert to LaTeX .tex
    pandoc_cmd = 'pandoc'
    if os.name == 'nt':
        # If pandoc is not in path, try to find it in local AppData
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        if local_appdata:
            local_pandoc = os.path.join(local_appdata, 'Pandoc', 'pandoc.exe')
            if os.path.exists(local_pandoc):
                pandoc_cmd = local_pandoc
                
    cmd = [pandoc_cmd, temp_md_path, '--listings', '-f', 'markdown', '-t', 'latex', '-o', tex_path]
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully compiled {filename} -> {tex_path}")
        
        # 6. Post-process the generated .tex file to replace \passthrough{\lstinline!...!} with \texttt{...}
        if os.path.exists(tex_path):
            with open(tex_path, 'r', encoding='utf-8') as tf:
                tex_content = tf.read()
            
            # Replace \passthrough{\lstinline!...!} with \texttt{...} using regex supporting any delimiter
            tex_content = re.sub(r'\\passthrough\{\\lstinline(.)(.*?)\1\}', r'\\texttt{\2}', tex_content)
            
            with open(tex_path, 'w', encoding='utf-8') as tf:
                tf.write(tex_content)
            print(f"Post-processed: {tex_path}")
            
    except FileNotFoundError:
        print(f"Warning: Pandoc is not installed. Skipped converting {filename} to .tex.")
    except subprocess.CalledProcessError as e:
        print(f"Error running Pandoc on {filename}: {e}")
    finally:
        # Clean up temporary processed markdown file
        if os.path.exists(temp_md_path):
            os.remove(temp_md_path)

def main():
    # Directories
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    docs_dir = os.path.join(root_dir, 'docs')
    chapters_dir = os.path.join(root_dir, 'chapters')
    images_dir = os.path.join(docs_dir, 'images')
    
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    
    # Find all documentation markdown files
    md_files = []
    for f in os.listdir(docs_dir):
        if f.endswith('.md') and f[0].isdigit():
            md_files.append(os.path.join(docs_dir, f))
            
    # Sort files by name so they run in order (00, 01, 02, etc.)
    md_files.sort()
    
    print(f"Found {len(md_files)} markdown documents to process.")
    for md_file in md_files:
        convert_md_file(md_file, chapters_dir, images_dir)

if __name__ == '__main__':
    main()
