# Persons Direction of Travel
Using the ADLINK Edge AI hardware and software to build a solution that counts the number of people waiting in line outside a retail store. The solution uses machine vision to estimate the number of people by doing an intersection between the people detected and a virtual line.

## Things we used in this project
### Hardware components
- ADLINK Vizi-AI

### Software components
- [ADLINK Edge SDK](https://www.adlinktech.com/en/Edge-SDK-IoT)
- [Intel Distribution of OpenVINO](https://software.intel.com/content/www/us/en/develop/tools/openvino-toolkit.html)
- [ADLINK Edge Utilities](https://github.com/tobymcclean/adl_edge_iot)

### Pre-trained Models
- [person-detection-retail-0013](https://docs.openvinotoolkit.org/2020.3/_models_intel_person_detection_retail_0013_description_person_detection_retail_0013.html)

## The story
A project inspired by [Retail Pandemic Reference Implementation - One Way Monitor](https://github.com/intel-iot-devkit/one-way-monitoring)

In many of the worker safety and social-distancing solutions we are seeing it is useful to be able to determine the direction of travel of people. In this project we use a Deep Learning model to detect people in a cameras field of view, and computer vision techniques to reidentify people. We can then use this information to determine the direction of travel for that person.

Some of the use cases where this applies are:
1. Counting the number of people in a building by counting the number of people who enter and exit,
2. In retail and industrial where there is a one way direction of travel identifying persons who are not adhering and notify them immediately, and
3. In worker safety application where a person's direction of travel may result in them being put in a dangerous situation.

## So how did we do it
- Define a  Intel Deep Learning Streamer pipeline that detects and tracks persons and publishes the bounding boxes and identities (a unique integer) for the persons to the ADLINK Data River using the DetectionBox data model.
- A Python application the associates a direction with each identity, by reading the DetectionBox stream from the Data River. The direction is then published to the Data River using the Person Direction data model.

## The devil is in the details

# References
Project inspired by [Retail Pandemic Reference Implementation - Line Monitoring](https://github.com/intel-iot-devkit/line-monitoring)
