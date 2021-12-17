#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

import datetime
import json
from pymongo import MongoClient
import requests
import sys
import time
import uuid

import ls_helper

try:
	if sys.argv[1] == 'all':
		#get all distinct wallet addr
		obj_client = MongoClient()
		obj_db = obj_client["lscores"]
		obj_coll = obj_db["lscores"]
		lst_dist = obj_coll.distinct("address")
		for str_wadd in lst_dist:
			ls_helper.get_wallet_obj(str_wadd)	
except Exception as e:
	print(e)
finally:
	print('...done')