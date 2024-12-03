import os
import subprocess

def build_and_package_docker(dockerfile, tag, output_dir):
    print(f"Building Docker image for {tag}...")
    try:
        # Build the Docker image
        subprocess.run(['docker', 'build', '-t', tag, '-f', dockerfile, '.'], check=True)
        print(f"Docker image for {tag} built successfully.")
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Run the Docker container and copy the output to the host
        subprocess.run(['docker', 'run', '--rm', '-v', f"{os.path.abspath(output_dir)}:/output", tag], check=True)
        print(f"Packaging for {tag} completed successfully. Executable is in '{output_dir}' folder.")
    except subprocess.CalledProcessError as e:
        print(f"Error during Docker build/run for {tag}: {e}")

def main():
    output_dir = 'dist'

    print("Building for windows...")
    subprocess.run(["pyinstaller", '--onefile', '--clean', '--windowed', '--add-data', 'icon.png:.', '--icon', 'icon.ico', '--name', 'Chat-DDP-Extended-Windows-amd64', 'main.py'], check=True)
    
    # Build and package for Linux
    build_and_package_docker('Dockerfile.linux', 'chat-ddp-extended-linux', output_dir)

if __name__ == '__main__':
    main()
