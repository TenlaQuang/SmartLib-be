def fix_main():
    with open('main.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    start_idx = 0
    for i, line in enumerate(lines):
        if i > 10 and 'from fastapi import FastAPI' in line:
            start_idx = i
            break
            
    if start_idx > 0:
        new_content = ''.join(lines[start_idx:])
        # Fix the literal \n@app.get
        new_content = new_content.replace('\\n@app.get("/")', '@app.get("/")')
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Cleaned up duplicated main.py")
    else:
        print("No duplicate found started")

if __name__ == '__main__':
    fix_main()
