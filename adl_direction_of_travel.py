import logging as log
from dataclasses import dataclass, field
from typing import List, Tuple, Any
import typing

import math

from shapely.geometry import LineString, box, Polygon, Point

from collections import Counter, namedtuple, OrderedDict
from adl_map import Map

from adl_edge_iot.datariver.things.edge_thing import EdgeThing
from adl_edge_iot.datariver.utils import write_tag
from adlinktech.datariver import class_from_thing_input, class_from_thing_output, as_nvp_seq
from adlinktech.datariver import FlowState

from rx.subject import Subject

DirectionData = namedtuple('DirectionData', ['flow_id', 'id', 'direction'])


@dataclass
class TrackableObject:
    bbox: List[int]
    id: str
    centroids: List[Tuple[int, int]] = field(default_factory=list)
    updated: bool = field(default=False)


@dataclass
class ObjectTrackers(object):
    trackers: typing.Dict[str, TrackableObject] = field(default_factory=dict)
    disappeared: typing.OrderedDict[str, Any] = field(default_factory=OrderedDict)
    trackId_generator: int = field(default=0)
    max_disappeared: int = field(default=30)

    def similarity(self, trackers: List[TrackableObject]):

        if len(self.trackers) > 0:
            trackers_number = len(trackers)
            if trackers_number == 0:
                trackers_copy = self.trackers.copy()
                for tracker_id, data in trackers_copy.items():
                    self.disappeared[tracker_id] += 1
                    if self.disappeared[tracker_id] > self.max_disappeared:
                        del self.trackers[tracker_id]
                        del self.disappeared[tracker_id]
            else:
                for tracker in trackers:
                    if tracker.id in self.trackers:
                        self.trackers[tracker.id].bbox = tracker.bbox
                        self.trackers[tracker.id].centroids.append(tracker.centroids[0])
                        self.disappeared[tracker.id] = 0
                        self.trackers[tracker.id].updated = True
                    else:
                        self.trackers.update({tracker.id: tracker})
                        self.trackers[tracker.id].updated = True
                        self.disappeared.update({tracker.id: 0})
                if trackers_number <= len(self.trackers):
                    trackers_copy = self.trackers.copy()
                    for tracker_id, data in trackers_copy.items():
                        if not data.updated:
                            self.disappeared[tracker_id] += 1
                            if self.disappeared[tracker_id] > self.max_disappeared:
                                del self.trackers[tracker_id]
                                del self.disappeared[tracker_id]
                                continue
                        self.trackers[tracker_id].updated = False
        else:
            self.register(trackers)

    def register(self, trackers):
        for tracker in trackers:
            self.trackers.update({tracker.id: tracker})
            self.disappeared.update({tracker.id: 0})

    def clear(self):
        self.trackers.clear()
        self.disappeared.clear()


tag_to_value_property_map = {
    'obj_id': 'int32',
    'obj_label': 'string',
    'class_id': 'int32',
    'class_label': 'string',
    'x1': 'float32',
    'y1': 'float32',
    'x2': 'float32',
    'y2': 'float32',
    'probability': 'float32',
    'meta': 'string',
    'dist_x': 'float64',
    'dist_y': 'float64',
    'dist_z': 'float64'
}


def get_polygon(point_list):
    return Polygon(point_list)


def get_box(points_tuple):
    return box(*points_tuple)


def get_line(data):
    return LineString(data)


class DirectionSensor(EdgeThing):
    def __init__(self, width, height, class_id, class_label, coords,
                 config_uri: str = '',
                 properties_str: str = '',
                 tag_group_dir: str = './definitions/TagGroup',
                 thing_class_dir: str = './definitions/ThingClass',
                 tag_groups: tuple = tuple(),
                 thing_cls: tuple = tuple()):
        super().__init__(config_uri, properties_str, tag_group_dir, thing_class_dir, tag_groups, thing_cls)
        self.class_id = class_id
        self.class_label = class_label
        self.running = True
        self.total_frames = 0
        self.coords = coords
        self.results = {}
        self.confidence_threshold = 0.65
        self.polygon = None
        self.line = None
        self.trend = []
        self.most = 0
        self.counter = Counter()
        self.trend_window = 81
        self.width = width
        self.height = height
        self.__detection_box_cls = class_from_thing_input(self.dr, self.thing, 'DetectionBoxData')
        self.__direction_cls = class_from_thing_output(self.dr, self.thing, 'DirectionSensor')
        self.__input_subject = Subject()
        self.__input_subject.subscribe(observer=self.process_data)
        self.__output_subject = Subject()
        self.__output_subject.subscribe(observer=self.process_count)
        self.trackers = ObjectTrackers()
        self.opposite = ""
        self.samples_quantity = 10
        self.threshold_displacement = 20
        self.config_env()

    def config_env(self):
        line = ((int(self.coords[0][0] * self.width / 100), int(self.coords[0][1] * self.height / 100)),
                (int(self.coords[1][0] * self.width / 100), int(self.coords[1][1] * self.height / 100)))
        line = get_line(line)
        self.polygon = line.buffer(5)
        self.polygon = get_polygon(list(self.polygon.exterior.coords))

    def get_direction(self, direction):
        if self.direction in ['U', 'D']:
            if direction > 0:
                return 'D'
            elif direction > 0:
                return 'U'
        else:
            if direction > 0:
                return 'R'
            elif direction > 0:
                return 'L'
        return ''

    def process_data(self, data):
        if data.flow_state == FlowState.ALIVE and data.data.size() > 0:
            trackers = []
            for nvp in data.data:
                if nvp.name == 'data':
                    for inner_nvp in nvp.value.nvp_seq:
                        box_nvp_seq = inner_nvp.value.nvp_seq
                        box_data = Map()
                        for box_nvp in box_nvp_seq:
                            box_data[box_nvp.name] = getattr(box_nvp.value, tag_to_value_property_map[box_nvp.name])
                        res, trackable_obj = self.process_boxes(box_data)
                        if res:
                            trackers.append(trackable_obj)

            self.trackers.similarity(trackers)
            for track_id, v in self.trackers.trackers.items():
                if len(v.centroids) > self.samples_quantity:
                    centroids = v.centroids

                    if self.direction in ["U", "D"]:
                        y = [c[1] for c in centroids]
                        dire = sum(y[-2:]) / 2 - y[0]
                    else:
                        x = [c[0] for c in centroids]
                        dire = sum(x[-2:]) / - x[0]

                    if math.sqrt(dire ** 2) < self.threshold_displacement:
                        continue

                    direction = self.get_direction(dire)
                    self.__output_subject.on_next(DirectionData(data.flow_id, track_id, direction))

    def process_box(self, box_data):
        xmin = int(box_data['x1'] * self.width)
        xmax = int(box_data['x2'] * self.width)
        ymin = int(box_data['y1'] * self.height)
        ymax = int(box_data['y2'] * self.height)

        c_x = int((xmin + xmax) / 2.0)
        c_y = int((ymin + ymax) / 2.0)

        point = Point([c_x, c_y])

        if self.polygon.contains(point):
            return True, TrackableObject([xmin, ymin, xmax, ymax], box_data['obj_id'], centroids=[(c_x, c_y)])
        else:
            return False, None

    def process_direction(self, direction_data):
        direction_obj = self.__direction_cls()
        direction_obj.class_id = self.class_id
        direction_obj.class_label = self.class_label
        direction_obj.id = direction_data.id
        direction_obj.direction = direction_data.direction
        write_tag(self.thing, 'DirectionSensor', as_nvp_seq(direction_obj), flow=direction_data.flow_id)

    def run(self):
        log.info('Running')
        selector = self.thing.select('DetectionBoxData')
        while not self.terminate:
            samples = selector.read_iot_nvp(1000)

            for sample in samples:
                self.__input_subject.on_next(sample)
