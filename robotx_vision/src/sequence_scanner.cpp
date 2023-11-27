/*This node funtions are:
  + Detect light sequence of the light buoy
*/

//ROS libs
#include <ros/ros.h>
#include <ros/console.h>
#include <image_transport/image_transport.h>
#include <sensor_msgs/image_encodings.h>
#include <cv_bridge/cv_bridge.h>
#include <robotx_vision/object_detection.h>

//OpenCV libs
#include <opencv2/opencv.hpp>
#include <opencv2/core/core.hpp>
#include <opencv2/calib3d/calib3d.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>

//C++ standard libs
#include <iostream>
#include <stdio.h>
#include <stdlib.h>
#include <string>
#include <vector>
#include <cmath>


//Namespaces
using namespace ros;
using namespace cv;
using namespace std;

//ROS params
std::string subscribed_image_topic;
std::string frame_id;
std::string output_topic_name;
bool debug;

//Image transport vars
cv_bridge::CvImagePtr cv_ptr;

//Must-have var
vector<sensor_msgs::RegionOfInterest> object;

//OpenCV image processing method dependent vars 
std::vector<std::vector<cv::Point> > contours;
std::vector<cv::Vec4i> hierarchy;
//std::vector<cv::Point> approx;
cv::Mat src, hsv, hls;
cv::Mat lower_hue_range;
cv::Mat upper_hue_range;
cv::Mat color;
cv::Mat str_el = cv::getStructuringElement(cv::MORPH_RECT, cv::Size(3,3));
cv::Rect rect;
cv::RotatedRect mr;
int height, width;
int min_area = 1500;
double area, m_area;
const double eps = 0.15;

//Code scanner vars
vector<std::string> color_sequence;
double sample_area;

//Functions
void setLabel(cv::Mat& im, std::vector<cv::Point>& contour, const double area)
{
  std::ostringstream strs;
  strs << area;
  std::string label = strs.str();
  int fontface = cv::FONT_HERSHEY_SIMPLEX;
  double scale = 0.4;
  int thickness = 1;
  int baseline = 0;

  cv::Size text = cv::getTextSize(label, fontface, scale, thickness, &baseline);
  cv::Rect r = cv::boundingRect(contour);

  cv::Point pt(r.x + ((r.width - text.width) / 2), r.y + ((r.height + text.height) / 2));
  cv::rectangle(im, pt + cv::Point(0, baseline), pt + cv::Point(text.width, -text.height), CV_RGB(255,255,255), CV_FILLED);
  cv::putText(im, label, pt, fontface, scale, CV_RGB(0,0,0), thickness, 10);
}

void reduce_noise(cv::Mat* dst)
{
  cv::morphologyEx(*dst, *dst, cv::MORPH_CLOSE, str_el);
  cv::morphologyEx(*dst, *dst, cv::MORPH_OPEN, str_el);
}

sensor_msgs::RegionOfInterest object_return()
{
  sensor_msgs::RegionOfInterest obj;
  obj.x_offset = (rect.tl()).x;
  obj.y_offset = (rect.tl()).y;
  obj.height = rect.height;
  obj.width = rect.width;
  obj.do_rectify = true;
  return obj;
}

void object_found()
{
  object.push_back(object_return());         //Push the object to the vector
  if(debug) cv::rectangle(src, rect.tl(), rect.br()-cv::Point(1,1), cv::Scalar(0,255,255), 2, 8, 0);
}

int is_white(cv::Point2f vtx)
{
  const double ref = 10;
  int x = (ref+1)*vtx.x/ref - mr.center.x/ref;
  int y = (ref+1)*vtx.y/ref - mr.center.y/ref;
  Vec3b pixel = hls.at<Vec3b>(cv::Point(x,y));
  if((int)pixel.val[1]>200) return 1;
  return 0;
}

int check_white_bounded()
{
  cv::Point2f vtx[4];
  mr.points(vtx);
  if(is_white(vtx[1]) && is_white(vtx[2]) && is_white(vtx[3])) return 1;
  return 0;
}

int rect_detect(std::string obj_color, cv::Scalar up_lim, cv::Scalar low_lim, cv::Scalar up_lim_wrap = cv::Scalar(0,0,0), cv::Scalar low_lim_wrap = cv::Scalar(0,0,0))
{
  //Filter desired color
  if(up_lim_wrap == low_lim_wrap)
    cv::inRange(hsv, up_lim, low_lim, color);
  else
  {//In case of red color
    cv::inRange(hsv, up_lim, low_lim, lower_hue_range);
    cv::inRange(hsv, up_lim_wrap, low_lim_wrap, upper_hue_range);
    cv::addWeighted(lower_hue_range,1.0,upper_hue_range,1.0,0.0,color);
  }
  //Reduce noise
  reduce_noise(&color);
  //if(debug) cv::imshow("color",color);
  //Finding shapes
  cv::findContours(color.clone(), contours, hierarchy, CV_RETR_TREE, CV_CHAIN_APPROX_SIMPLE);
  //Traverse through each contour and analyze
  for (int i = 0; i < contours.size(); i++)
  {
    // Approximate contour with accuracy proportional to the contour perimeter
    //cv::approxPolyDP(cv::Mat(contours[i]), approx, cv::arcLength(cv::Mat(contours[i]), true)*0.01, true);
    // Skip small objects 
    if (std::fabs(cv::contourArea(contours[i])) < min_area) continue;
    //Find the object
    rect = cv::boundingRect(contours[i]);
    mr = cv::minAreaRect(contours[i]);
    //if(check_white_bounded()) //Check if object is in front of a white background
    {
      area = cv::contourArea(contours[i]);
      m_area = (mr.size).height*(mr.size).width;
      if(debug) setLabel(src, contours[i], area);
      
      if((fabs(1.0-area/m_area) < eps) && (rect.height > rect.width))
      {
        object_found();
        return 1;
      }
    }
    return 0;
  }
}

void imageCb(const sensor_msgs::ImageConstPtr& msg)
{
  try
  {
    cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::BGR8);
  }
  catch (cv_bridge::Exception& e)
  {
    ROS_ERROR("cv_bridge exception: %s", e.what());
    return;
  }

  //Get the image in OpenCV format
  src = cv_ptr->image;
  //newImage = true;

  //Start the shape detection code
  if(src.empty()) return;
  cv::cvtColor(src,hsv,COLOR_BGR2HSV);
  cv::cvtColor(src,hls,COLOR_BGR2HLS);
  width = src.cols;
  height = src.rows;
  //Detect a black rect first
  if(rect_detect("black", cv::Scalar(0, 0, 0), cv::Scalar(179, 255, 5)))
  {
    if(m_area > sample_area) sample_area = m_area;
    color_sequence.clear();
    ROS_INFO("Found black, start scanning...");
  }
  //Detecting other colors depending on the bgyr[] array assignment
  //BLUE
  if(color_sequence.empty() || (color_sequence.back() != "blue"))
  	if(rect_detect("blue", cv::Scalar(90, 250, 90), cv::Scalar(130, 255, 255)) && (fabs(m_area/sample_area - 1) < (eps+0.1)))
      color_sequence.push_back("blue");
  //GREEN
  if(color_sequence.empty() || (color_sequence.back() != "green"))
  	if(rect_detect("green", cv::Scalar(50, 200, 200), cv::Scalar(80, 255, 255)) && (fabs(m_area/sample_area - 1) < (eps+0.1)))
      color_sequence.push_back("green");
  //YELLOW
  if(color_sequence.empty() || (color_sequence.back() != "yellow"))
  	if(rect_detect("yellow", cv::Scalar(20, 80, 100), cv::Scalar(30, 255, 255)) && (fabs(m_area/sample_area - 1) < (eps+0.1)))
      color_sequence.push_back("yellow");
  //RED
  if(color_sequence.empty() || (color_sequence.back() != "red"))
  	if(rect_detect("red", cv::Scalar(0, 80, 100), cv::Scalar(10, 255, 255), cv::Scalar(165, 80, 100), cv::Scalar(176, 255, 255)) && (fabs(m_area/sample_area - 1) < (eps+0.1)))
    	color_sequence.push_back("red");
	if(debug && (color_sequence.size() > 0))
	{
		for(vector<std::string>::iterator its = color_sequence.begin(); its != color_sequence.end(); ++its)
			cout << *its << "-";
		cout << endl;
	}
  if(color_sequence.size()==3)
  {
    ros::param::set("/gui/color1", color_sequence[0]);
    ros::param::set("/gui/color2", color_sequence[1]);
    ros::param::set("/gui/color3", color_sequence[2]);
    ros::shutdown(); //Shutdown when job is done
  }
  //Show output on screen
  if(debug)
  {
  	cv::imshow("src", src);
  }
}

int main(int argc, char** argv)
{
  //Initiate node
  ros::init(argc, argv, "object_detector");
  ros::NodeHandle nh;
  ros::NodeHandle pnh("~");
  pnh.getParam("subscribed_image_topic", subscribed_image_topic);
  pnh.getParam("debug", debug);
  pnh.getParam("output_topic_name", output_topic_name);

  //Initiate windows
  if(debug)
  {
	  cv::namedWindow("src",WINDOW_AUTOSIZE);
	  cv::resizeWindow("src",640,480);
	  //cv::namedWindow("color",WINDOW_AUTOSIZE);
	  //cv::resizeWindow("color",640,480);
	  cv::startWindowThread();
	}

  //Start ROS subscriber...
  image_transport::ImageTransport it(nh);
  image_transport::Subscriber sub = it.subscribe(subscribed_image_topic, 1, imageCb);

  //...and ROS publisher
  ros::Publisher pub = nh.advertise<sensor_msgs::RegionOfInterest>(output_topic_name, 1000);
  ros::Rate rate(2);

  while (nh.ok())
  {
    //Publish every object detected
    for(vector<sensor_msgs::RegionOfInterest>::iterator it = object.begin(); it != object.end(); it++)
      pub.publish(*it);
    //Reinitialize the object counting vars
    object.clear();
    //Do imageCb function and go to sleep
    ros::spinOnce();
    rate.sleep();
  }
  cv::destroyAllWindows();
  return 0;
}