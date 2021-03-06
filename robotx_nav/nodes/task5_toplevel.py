#!/usr/bin/env python

""" Mission 5-CORAL SURVEY

	Set map border, size and origin
	Set quadrants of interest

	Do zigzag scouting to respective quadrants (perpetual)
	If shape identified or duration timeout
		Shape identified->set global parameter for gui
	continue to next quadrant

   If both shapes identified or total time exceeded, terminate mission

task 5:
	-----------------
	Created by Reinaldo@ 2016-12-06
	Authors: Reinaldo
	-----------------


"""
import rospy
import multiprocessing as mp
import math
import time
import numpy as np
import os
import tf
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Pose
from visualization_msgs.msg import MarkerArray, Marker
from move_base_forward import Forward
from move_base_zigzag import Zigzag
from move_base_force_cancel import ForceCancel
from tf.transformations import euler_from_quaternion
from nav_msgs.msg import Odometry

def constant_heading(goal):
	print("const_heading")
	constant_obj = Forward(nodename="constant_heading", target=goal, waypoint_separation=5, is_relative=False)

def cancel_zigzag():
	print("kill zigzag")
	os.system('rosnode kill zigzag')


def zigzag(quadrant=1, map_length=40, map_width=40, half_period=4, half_amplitude=9, offset=3):
	print("zigzag starts")
	zigzag=Zigzag(nodename="zigzag", quadrant=quadrant, map_length=map_length, map_width=map_width, half_period=half_period, half_amplitude=half_amplitude, offset=offset)
	print("zigzag returns")


class CoralSurvey(object):
	pool = mp.Pool()

	x0, y0, yaw0= 0, 0, 0

	shape_counter=0
	shape_found=[0, 0, 0] #Tri, Cru , Cir
	current_quadrant=0
	map_length=40  #x direction
	map_width=40 #y direction
	half_period=4
	half_amplitude=9
	offset=3


	def __init__(self, quadrant_list):
		print("starting task 5")
		rospy.init_node('task_5', anonymous=True)
		rospy.Subscriber("/filtered_marker_array", MarkerArray, self.marker_callback, queue_size = 50)
		self.marker_pub= rospy.Publisher('waypoint_markers', Marker, queue_size=5)

		self.base_frame = rospy.get_param("~base_frame", "base_link")
		self.fixed_frame = rospy.get_param("~fixed_frame", "map")
		# tf_listener
		self.tf_listener = tf.TransformListener()
		self.odom_received = False
		rospy.wait_for_message("/odometry/filtered/global", Odometry)
		rospy.Subscriber("/odometry/filtered/global", Odometry, self.odom_callback, queue_size=50)
		while not self.odom_received:
		   rospy.sleep(1)
		print("odom received")

		self.quadrant_visited=list()
		self.doing_zigzag=list()

		for i in range(len(quadrant_list)):
			self.quadrant_visited.append(0) #not visited
			self.doing_zigzag.append(0)

		while not rospy.is_shutdown():
			#main loop

			#visit quadrant that is not yet visited
			for i in range(len(quadrant_list)):
				if self.quadrant_visited[i]==0:
					self.current_quadrant=i
					break
						
			if self.doing_zigzag[self.current_quadrant]==0:
				self.pool.apply_async(zigzag, args=(quadrant_list[self.current_quadrant], self.map_length, self.map_width, self.half_period, self.half_amplitude, self.offset, ))
				self.doing_zigzag[self.current_quadrant]=1

		
			time.sleep(1)
	
		self.pool.close()
		self.pool.join()

	def is_complete(self):
		pass

	def marker_callback(self, msg):


		if len(msg.markers)>0:

			if msg.markers[0].type == 0 and self.shape_found[0]==0:
				#triangle

				if self.shape_counter==0:
					rospy.set_param("/gui/shape1", "TRI")
					self.shape_counter+=1
				elif self.shape_counter==1:
					rospy.set_param("/gui/shape2", "TRI")
				self.shape_found[0]=1
				self.quadrant_visited[self.current_quadrant]=1
				self.pool.apply(cancel_zigzag)
				print("found Triangle")

			elif msg.markers[0].type == 1 and self.shape_found[1]==0:
				#cruciform
				if self.shape_counter==0:
					rospy.set_param("/gui/shape1", "CRU")
					self.shape_counter+=1
				elif self.shape_counter==1:
					rospy.set_param("/gui/shape2", "CRU")

				self.shape_found[1]=1
				self.quadrant_visited[self.current_quadrant]=1
				self.pool.apply(cancel_zigzag)
				print("found Crux")

			elif msg.markers[0].type == 2 and self.shape_found[2]==0:
				#circle
				if self.shape_counter==0:
					rospy.set_param("/gui/shape1", "CIR")
					self.shape_counter+=1
				elif self.shape_counter==1:
					rospy.set_param("/gui/shape2", "CIR")

				self.shape_found[2]=1
				self.quadrant_visited[self.current_quadrant]=1
				self.pool.apply(cancel_zigzag)
				print("found Circle")


	def get_tf(self, fixed_frame, base_frame):
		""" transform from base_link to map """
		trans_received = False
		while not trans_received:
			try:
				(trans, rot) = self.tf_listener.lookupTransform(fixed_frame,
																base_frame,
																rospy.Time(0))
				trans_received = True
				return (Point(*trans), Quaternion(*rot))
			except (tf.LookupException,
					tf.ConnectivityException,
					tf.ExtrapolationException):
				pass

	def odom_callback(self, msg):
		trans, rot = self.get_tf("map", "base_link")
		self.x0 = trans.x
		self.y0 = trans.y
		_, _, self.yaw0 = euler_from_quaternion((rot.x, rot.y, rot.z, rot.w))
		self.odom_received = True



if __name__ == '__main__':
	try:
		CoralSurvey([1, 3])

		# stage 1: gps
	except rospy.ROSInterruptException:
		rospy.loginfo("Task 5 Finished")
