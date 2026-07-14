#!/usr/bin/env python3
import subprocess
import sys

def run_command(command, description):
    print(f"[*] Running: {description}...")
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"[!] Error during: {description}")
        print(result.stdout)
        print(result.stderr)
        return False
    print(f"[+] Success: {description}")
    if result.stdout.strip():
        print(result.stdout.strip())
    return True

def main():
    # 1. Run site generator
    if not run_command("python3 generator.py", "Static Site Generator Rebuild"):
        sys.exit(1)
        
    # 2. Check git status to see if there are updates
    print("[*] Checking git status...")
    status_res = subprocess.run("git status --porcelain", shell=True, stdout=subprocess.PIPE, text=True)
    if not status_res.stdout.strip():
        print("[+] No changes to deploy. Site is up to date!")
        sys.exit(0)
        
    # 3. Add files to git
    if not run_command("git add -A", "Git staging"):
        sys.exit(1)
        
    # 4. Commit changes
    commit_msg = "UI: Update layout spacings, distinct markers, SVG bottle themes, original star coin face, agent floating widget, and border glows"
    if len(sys.argv) > 1:
        commit_msg = sys.argv[1]
    if not run_command(f'git commit -m "{commit_msg}"', "Git commit"):
        sys.exit(1)
        
    # 5. Push to GitHub
    if not run_command("git push origin main", "Git push to origin main"):
        sys.exit(1)
        
    print("[+] Deployment completed successfully! Live site will update in a few moments.")

if __name__ == '__main__':
    main()
