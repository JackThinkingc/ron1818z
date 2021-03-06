#!/usr/bin/env python

""" Mission 7-Detect and Deliver

	
	1. Random walk with gaussian at center of map until station position is acquired
	2. loiter around until correct face seen
	3. if symbol seen, move towards symbol perpendicularly
	4. if close enough, do move_base aiming

task 7:
	-----------------
	Created by Reinaldo@ 2016-12-07
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
from sklearn.cluster import KMeans
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Pose, Quaternion
from visualization_msgs.msg import MarkerArray, Marker
from move_base_forward import Forward
from move_base_waypoint import MoveTo
from move_base_loiter import Loiter
from move_base_stationkeeping import StationKeeping
from tf.transformations import quaternion_from_euler, euler_from_quaternion
from std_msgs.msg import Int8


class DetectDeliver(object):


	MAX_DATA=3
	x0, y0, yaw0= 0, 0, 0
	symbol=[0 , 0]
	symbols=np.zeros((MAX_DATA, 2)) #unordered list
	symbols_counter=0
	angle_threshold=10*math.pi/180

	symbol_location=np.zeros((MAX_DATA, 2))

	shape_counter=0

	distance_to_box=2

	def __init__(self, symbol_list):
		print("starting task 7")
		rospy.init_node('task_7', anonymous=True)

		self.symbol=symbol_list
		self.symbol_visited=0	
		self.symbol_seen=False
		self.symbol_position=[0, 0, 0] 
		self.station_seen=False #station here is cluster center of any face
		self.station_position=[0, 0]

		self.loiter_obj = Loiter("loiter", is_newnode=False, target=None, radius=5, polygon=4, mode=1, mode_param=1, is_relative=False)
		self.moveto_obj = MoveTo("moveto", is_newnode=False, target=None, is_relative=False)
		self.stationkeep_obj = StationKeeping("station_keeping", is_newnode=False, target=None, radius=2, duration=30)

		rospy.Subscriber("/filtered_marker_array", MarkerArray, self.symbol_callback, queue_size = 50)
		#rospy.Subscriber("/shoot", MarkerArray, self.symbol_callback, queue_size = 50)
		rospy.Subscriber("/finished_search_and_shoot", Int8, self.stop_shoot_callback, queue_size = 5)
		self.shooting_pub= rospy.Publisher('/start_search_and_shoot', Int8, queue_size=5)
		self.marker_pub= rospy.Publisher('/waypoint_markers', Marker, queue_size=5)

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

		print(self.symbol)
		d=1
		while not rospy.is_shutdown() and not self.station_seen:
			target=[self.x0+d*math.cos(self.yaw0), self.y0+d*math.sin(self.yaw0), self.yaw0]

			self.moveto_obj.respawn(target, )#forward 

		print("station: ")
		print(self.station_position)
		#aiming to the box
		self.shooting_complete=False
		self.is_aiming=False

		#loiter around station until symbol's face seen

		while not rospy.is_shutdown():
			theta=math.atan2(self.station_position[1]-self.y0, self.station_position[0]-self.x0)
			target=[self.station_position[0], self.station_position[1], theta]
			self.move_to_goal(target, )
			if self.distance_from_boat(target)<6:
				self.shooting_pub.publish(1)
				break

		loiter_radius=math.sqrt((self.x0-self.station_position[0])**2+(self.y0-self.station_position[1])**2)

		if loiter_radius>5:
			loiter_radius=3	

		while not rospy.is_shutdown():
			print(loiter_radius)
			self.loiter_obj.respawn(self.station_position, 4, loiter_radius, )
			self.shooting_pub.publish(1)
			if loiter_radius>3:
				loiter_radius-=1

			if self.symbol_seen:
				print(self.symbol_position)
				print("symbol's position acquired, exit loitering")
				break

			if self.shooting_complete:
				print("shooting done, return to base")		
				break

			time.sleep(1)
	

		print(self.symbol_position)
		d=math.sqrt((self.x0-self.symbol_position[0])**2+(self.y0-self.symbol_position[1])**2)
		counter=0
		print(d)

		#moveto an offset, replan in the way
		while not rospy.is_shutdown():
			self.shooting_pub.publish(1)
			alpha=self.yaw0-self.symbol_position[2]
			theta=math.atan2(math.fabs(math.sin(alpha)), math.fabs(math.cos(alpha))) #always +ve and 0-pi/2
			d=math.sqrt((self.x0-self.symbol_position[0])**2+(self.y0-self.symbol_position[1])**2)
			perpendicular_d=0.6*d*math.cos(theta)

			if counter ==0 or theta>self.angle_threshold or d>self.distance_to_box:
				print("replan")
				target=[self.symbol_position[0]+perpendicular_d*math.cos(self.symbol_position[2]),self.symbol_position[1]+perpendicular_d*math.sin(self.symbol_position[2]), -self.symbol_position[2]]

				self.moveto_obj.respawn(target, )
				counter+=1

			if d<self.distance_to_box:
				break
			time.sleep(1)	

			if self.shooting_complete:
				print("shooting done, return to base")		
				break
		
		


		station=[self.x0, self.y0, -self.symbol_position[2]]
		radius=2
		duration=30
		print(self.symbol_position)
		print(station)
		while not rospy.is_shutdown():
			self.shooting_pub.publish(1)
			#duration 0 is forever
			if not self.is_aiming:			
				self.stationkeep_obj.respawn(station, radius, duration)
				#make aiming respawn
			
			if self.shooting_complete:
				print("shooting done, return to base")		
				break

			time.sleep(1)

	def distance_from_boat(self, target):
		return math.sqrt((target[0]-self.x0)**2+(target[1]-self.y0)**2)

	def move_to_goal(self, goal):
		print("move to point")
		one_third_goal=[2*self.x0/3+goal[0]/3, 2*self.y0/3+goal[1]/3, math.atan2(goal[1]-self.y0, goal[0]-self.x0)]
		print(one_third_goal)
		self.moveto_obj.respawn(one_third_goal, )


	def stop_shoot_callback(self, msg):
		if msg.data==1:
			#stop aiming station
			self.shooting_complete=True
		

	def symbol_callback(self, msg):
		if len(msg.markers)>0:
			if self.symbols_counter>self.MAX_DATA:
				   
				station_kmeans = KMeans(n_clusters=1).fit(self.symbols)
				self.station_center=station_kmeans.cluster_centers_

				self.station_position[0]=self.station_center[0][0]
				self.station_position[1]=self.station_center[0][1]
				self.station_seen=True
	

			for i in range(len(msg.markers)):

				self.symbols[self.symbols_counter%self.MAX_DATA]=[msg.markers[i].pose.position.x, msg.markers[i].pose.position.y]
				self.symbols_counter+=1
		
				if msg.markers[i].type==self.symbol[0] and msg.markers[i].id==self.symbol[1]:
					#set position_list (not sure)
					self.symbol_position[0]=msg.markers[i].pose.position.x
					self.symbol_position[1]=msg.markers[i].pose.position.y
					x = msg.markers[i].pose.orientation.x
					y = msg.markers[i].pose.orientation.y
					z = msg.markers[i].pose.orientation.z
					w = msg.markers[i].pose.orientation.w
					_, _, self.symbol_position[2] = euler_from_quaternion((x, y, z, w))

					self.symbol_location[self.shape_counter%self.MAX_DATA]=[msg.markers[i].pose.position.x, msg.markers[i].pose.position.y]
					self.shape_counter+=1
		
				if self.station_seen and self.shape_counter>self.MAX_DATA:
					symbol_kmeans = KMeans(n_clusters=1).fit(self.symbol_location)
					self.symbol_center=symbol_kmeans.cluster_centers_
					self.symbol_position[0]=self.symbol_center[0][0]
					self.symbol_position[1]=self.symbol_center[0][1]
					#print(self.symbol_position)
					self.symbol_seen=True

			#self.pool.apply(cancel_loiter)

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
	#[id,type]cruciform red
		DetectDeliver([1,0])

	except rospy.ROSInterruptException:
		rospy.loginfo("Task 7 Finished")
