# WebBurner
Flask-based app that allows you to upload music from a device on your network and burn a CD using a compatible disc drive on the server machine.
## Debian / Linux Installation:
INSTALL ON HOST SYSTEM WITH DISC DRIVE
Install dependencies:
```
sudo apt update
sudo apt install ffmpeg wodim python3 python3-flask
```
Run the python script
webpage will be available in a web browser within the network by navigating to:
### <IP OF HOST MACHINE>:8080

This port can be changed at the very bottom of the script if 8080 is already taken.

## How to use:
1. Navigate to <IP OF HOST MACHINE>:8080 on a web browser within your network
2. Place a blank CD in the disc drive of host machine (CD-R reccommended)
3. Use the upload button to select the music files you would like to burn (MP3 or WAV only for now)
4. make sure the total length of music does not exceed 80 minutes (have not tested if it properly stops you from doing so)
4. click burn
>hopeful success.

Still a work in progress. contact me with any issues and I will try to resolve them.
