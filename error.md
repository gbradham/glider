lsusb | grep -i cam
Bus 001 Device 003: ID 3938:1299 Sonix Technology Co., Ltd. onn. USB 2.0 webcam
(venv) RP3@RP3:~/glider $ ls -la /dev/video*
crw-rw----+ 1 root video 81, 17 Jan  2 11:10 /dev/video0
crw-rw----+ 1 root video 81, 18 Jan  2 11:10 /dev/video1
crw-rw----+ 1 root video 81,  8 Dec 31 10:40 /dev/video19
crw-rw----+ 1 root video 81,  0 Dec 31 10:40 /dev/video20
crw-rw----+ 1 root video 81,  1 Dec 31 10:40 /dev/video21
crw-rw----+ 1 root video 81,  2 Dec 31 10:40 /dev/video22
crw-rw----+ 1 root video 81,  3 Dec 31 10:40 /dev/video23
crw-rw----+ 1 root video 81,  4 Dec 31 10:40 /dev/video24
crw-rw----+ 1 root video 81,  5 Dec 31 10:40 /dev/video25
crw-rw----+ 1 root video 81,  6 Dec 31 10:40 /dev/video26
crw-rw----+ 1 root video 81,  7 Dec 31 10:40 /dev/video27
crw-rw----+ 1 root video 81,  9 Dec 31 10:40 /dev/video28
crw-rw----+ 1 root video 81, 10 Dec 31 10:40 /dev/video29
crw-rw----+ 1 root video 81, 11 Dec 31 10:40 /dev/video30
crw-rw----+ 1 root video 81, 12 Dec 31 10:40 /dev/video31
crw-rw----+ 1 root video 81, 13 Dec 31 10:40 /dev/video32
crw-rw----+ 1 root video 81, 14 Dec 31 10:40 /dev/video33
crw-rw----+ 1 root video 81, 15 Dec 31 10:40 /dev/video34
crw-rw----+ 1 root video 81, 16 Dec 31 10:40 /dev/video35
(venv) RP3@RP3:~/glider $ groups
RP3 adm dialout cdrom sudo audio video plugdev games users input render netdev lpadmin gpio i2c spi
(venv) RP3@RP3:~/glider $ v4l2-ctl --list-formats-ext -d /dev/video0
ioctl: VIDIOC_ENUM_FMT
	Type: Video Capture

	[0]: 'MJPG' (Motion-JPEG, compressed)
		Size: Discrete 2592x1944
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 2560x1440
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 1920x1080
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 1280x1024
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 1280x720
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 960x540
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 848x480
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 800x600
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 640x480
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 320x240
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 160x120
			Interval: Discrete 0.033s (30.000 fps)
	[1]: 'YUYV' (YUYV 4:2:2)
		Size: Discrete 2592x1944
			Interval: Discrete 0.500s (2.000 fps)
		Size: Discrete 2560x1440
			Interval: Discrete 0.500s (2.000 fps)
		Size: Discrete 1920x1080
			Interval: Discrete 0.500s (2.000 fps)
		Size: Discrete 1280x1024
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 1280x720
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 960x540
			Interval: Discrete 0.067s (15.000 fps)
		Size: Discrete 848x480
			Interval: Discrete 0.050s (20.000 fps)
		Size: Discrete 800x600
			Interval: Discrete 0.050s (20.000 fps)
		Size: Discrete 640x480
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 320x240
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 160x120
			Interval: Discrete 0.033s (30.000 fps)

