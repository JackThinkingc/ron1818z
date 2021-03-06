#!/usr/bin/env python

'''
MSER detector demo
==================

Usage:
------
    mser.py [<video source>]

Keys:
-----
    ESC   - exit

'''

import numpy as np
import cv2
# import video

if __name__ == '__main__':
    cam = cv2.VideoCapture(0)
    mser = cv2.MSER_create()
    while True:
        ret, img = cam.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vis = img.copy()

        regions = mser.detectRegions(gray)
        hulls = [cv2.convexHull(np.array(p).reshape(-1, 1, 2)) for p in regions]
        cv2.polylines(vis, hulls, 1, (0, 255, 0))

        cv2.imshow('img', vis)
        if 0xFF & cv2.waitKey(5) == 27:
            break
    cv2.destroyAllWindows()
