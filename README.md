# Extended Chat-DDP
@author: Vincent Valentino Oei

A simple chat bot based on a DDP-1 assignment, extended to support communication between devices in a local network, albeit **without encryption**.

This app also provides a simple scalable framework that is based on discord.py to build chatbots on top of.

## Usage

1. Run from source:
```sh
# Windows
python main.py 

# Unix-based systems 
python3 main.py
```


2. Run from the built binaries:
Download an executable suitable to your system (currently the only supported systems are windows and linux), and run it by double clicking it or from the terminal.


## Building binaries
To build the binaries, you'll have to install docker and pyinstaller.

To install docker, navigate to its website and follow their installation guide.

To install pyinstaller, simply:

```sh
# Windows
pip install pyinstaller

# Unix-based systems
pip3 install pyinstaller
```

After the dependencies are satistied, run:
```sh
# Windows
python app_packager.py

# Unix-based systems
python3 app_packager.py
```