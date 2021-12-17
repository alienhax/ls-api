#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

from bson import json_util, ObjectId
import datetime
from flask import Flask, jsonify, make_response, request
import json
from pymongo import MongoClient
import requests
import sys
import time
import uuid

import ls_helper

app = Flask(__name__)

@app.route('/getghostid', methods=['POST'])
def get_ghost_id():
	dct_json_data = request.get_json()
	str_uuid = uuid.uuid4().hex
	obj_client = MongoClient()
	obj_db = obj_client["ghostids"]
	obj_coll = obj_db['ghostids']

	is_gen = False
	str_uuid = uuid.uuid4().hex

	while is_gen == False:
		dct_doc = obj_db["ghostids"].find_one({'_id': str_uuid})
		if dct_doc is None: 
			is_gen = True
		else: 
			str_uuid = uuid.uuid4().hex

	#mongodb upsert
	obj_coll.update(
		{ "_id" : str_uuid },
		{ "ts" : datetime.datetime.now().timestamp() }, 
		upsert = True
	)

	return jsonify({ 'ghostid' : str_uuid })


@app.route('/getwalletinfo', methods=['POST'])
def get_wallet_info():
	dct_ret = { 'addressList' : [] }

	dct_json_data = request.get_json()
	lst_wadd = dct_json_data['wallets'] if 'wallets' in dct_json_data.keys() is not None else []

	for str_wadd in lst_wadd:
		obj_wadd = ls_helper.get_wallet_obj(str_wadd)
		dct_ret['addressList'].append(obj_wadd)

	return jsonify(dct_ret)

@app.route('/getwalletinfo-by-daterange', methods=['POST'])
def get_wallet_info_by_dr():
	dct_ret = { 'addressList' : [] }

	dct_json_data = request.get_json()
	lst_wadd = dct_json_data['wallets'] if 'wallets' in dct_json_data.keys() is not None else []
	dat_b = dct_json_data['start'] if 'start' in dct_json_data.keys() is not None else None
	dat_e = dct_json_data['end'] if 'start' in dct_json_data.keys() is not None else None

	if dat_b is not None and dat_e is not None:
		for str_wadd in lst_wadd:
			obj_wadd = ls_helper.get_wallet_objs(str_wadd,dat_b,dat_e)
			dct_ret['addressList'].append(obj_wadd)

	return jsonify(dct_ret)

@app.route('/getwalletdetails', methods=['POST'])
def get_wallet_details():
	lst_ret = []

	dct_json_data = request.get_json()
	lst_wadd = dct_json_data['wallets'] if 'wallets' in dct_json_data.keys() is not None else []
	dat_b = dct_json_data['startTime'] if 'startTime' in dct_json_data.keys() is not None else None
	dat_e = dct_json_data['endTime'] if 'endTime' in dct_json_data.keys() is not None else None

	if dat_b is not None and dat_e is not None:
		for str_wadd in lst_wadd:
			lst_wadd = ls_helper.get_wallet_det_objs(str_wadd,dat_b,dat_e)
			if len(lst_wadd) > 0:
				lst_ret += lst_wadd

	return jsonify(lst_ret)

if __name__ == '__main__':
	app.run(debug=True,host='0.0.0.0')