# -*- coding: utf-8 -*-
# TODO create time-domain graph
# https://pythontic.com/visualization/signals/spectrogram
import json
import collections
import pprint
from datetime import datetime

pp = pprint.PrettyPrinter(indent=4)


block_times = {}


def collectPageTime(page):
    try:
        time = datetime.fromtimestamp(int(page['create-time']) / 1000)
        # print(time)
    except KeyError:
        time = datetime.fromtimestamp(int(page['edit-time']) / 1000)
    collectBlockTime(page)


def collectBlockTime(object):
    '''Collects block children names and UUIDs'''
    block_ids = {}
    if 'children' in object.keys():
        for child in object['children']:
            block_ids[child['uid']] = child
            try:
                time = datetime.fromtimestamp(int(object['create-time']) / 1000).strftime("%Y%m%d")
                # print(time.strftime("%Y%m%d"))
                if time in block_times:
                    block_times[time].append(child['uid'])
                else:
                    block_times[time] = [child['uid']]
            except KeyError:
                time = datetime.fromtimestamp(int(object['edit-time']) / 1000).strftime("%Y%m%d")
                if time in block_times:
                    block_times[time].append(child['uid'])
                else:
                    block_times[time] = [child['uid']]
            collectBlockTime(child)
    # print(block_ids)


def main():
    # load json backup
    jsonFile = 'MattPublic.json'
    # read database json
    with open(jsonFile, 'r') as f:
        data = json.loads(f.read())
    for page in data:  # get page ids
        collectPageTime(page)

    # create an OrderedDict
    od = collections.OrderedDict(sorted(block_times.items()))
    for day in od:
        print(day, len(block_times[day]))


if __name__ == '__main__':
    main()
