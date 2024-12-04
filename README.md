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


### Using Cloudflared Tunnel to bypass NAT
First, make sure you have an installation of cloudflared ready for the server machine and the client machines outside the server's local network, if not, install it from [here](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).


#### Server Machine
First, run the server on the server machine by running '/startserver <PORT>' inside the app
with <PORT> as any available port on your system, if it is not given, <PORT> 
will default to 8080.

Then run the following command:
```sh
cloudflared tunnel -url tcp://localhost:<PORT>
```
Replace <PORT> with the port that you have used on the '/startserver <PORT>' command.

After running the following command, something similiar to the following will be shown in your terminal:
```
2024-12-04T03:55:27Z INF +--------------------------------------------------------------------------------------------+
2024-12-04T03:55:27Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2024-12-04T03:55:27Z INF |  https://mrs-done-arthritis-universities.trycloudflare.com                                 |
2024-12-04T03:55:27Z INF +--------------------------------------------------------------------------------------------+
```
In this case, the hostname will be `mrs-done-arthritis-universities.trycloudflare.com`.
Share that hostname with the users outside your local network. 


#### Client Machines
If the client is on the same local network as the server, simply follow the instruction given by the program.

Otherwise, on every client machine outside your local network, run:
```
cloudflared access tcp --hostname <HOSTNAME> --url localhost:<LOCALPORT>
```
Replace <HOSTNAME> with the hostname which the server is tunnelled to.
Replace <LOCALPORT> with any port that is currently free, usually a 4 digit number such as 8080, 6789, and any other port will suffice.

After running that command, run '/connect localhost <LOCALPORT>' in the app, 
where <LOCALPORT> is the same as the one used to run the previous command.


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