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

str_api_key = 'ETHERSCAN_API_KEY_HERE'
str_LED_add = '0x72de803b67b6ab05b61efab2efdcd414d16ebf6d'

int_min_score = 100
int_max_score = 1000
int_max_swing = int_max_score - int_min_score

dct_score_index = {
	'0-historical_behavior' : { 'weight' : .25 }, 
	'1-preferred_tokens' : { 'weight' : .25 },
	'2-get_lsrank_score' : { 'weight' : .15 },
	'3-get_trans_score' : { 'weight' : .35 }
}

def move_point(number, shift, base=10):
	return number * base**shift

def get_percent(a, b):
	result = int(((b - a) * 100) / a) if a != b else 100
	return result

##@app.route('/t10', methods=['POST'])
def get_t10_defi_tokens():
	lst_t10 = []
	try:
		#check if last record is for today - else grab / record new
		obj_client = MongoClient()
		obj_db = obj_client["tt"]
		obj_coll = obj_db["tt"]	
		dbl_ts = datetime.datetime.now().timestamp()
		dat_iso = datetime.datetime.fromtimestamp(dbl_ts, None)	

		#formatted_date = datetime.date.strftime(current_day, "%m/%d/%Y")
		dat_tod = datetime.datetime.today()
		str_dat_1 =  datetime.date.strftime(dat_tod, "%m/%d/%Y") 
		dat_1 = dat_tod.strptime(str_dat_1,"%m/%d/%Y")
		dat_tom = dat_tod + datetime.timedelta(days=1)
		str_dat_2 = datetime.date.strftime(dat_tom, "%m/%d/%Y")
		dat_2 = dat_tom.strptime(str_dat_2,"%m/%d/%Y")

		obj_lrec = obj_coll.find({ "$and" : [{'ts' : { "$gte" : dat_1.timestamp() }},{'ts' : { "$lte" : dat_2.timestamp() }}] },{'_id': False}).sort('ts',-1).limit(1)
		if obj_lrec is not None and obj_lrec.count() > 0: 
			lst_t10 = obj_lrec[0]['tt']
		else:
			str_url = "https://api.ethplorer.io/getTop?apiKey=freekey&criteria=cap"
			obj_response = requests.get(str_url)
			if obj_response.status_code == 200:
				obj_json = obj_response.json()
				if 'tokens' in obj_json.keys() and len(obj_json['tokens']) > 0:
					lst_t10 = obj_json['tokens'][:10]
					dct_this = {'tt' : lst_t10 ,'ts': dbl_ts}
					dct_ins = json.loads(json_util.dumps(dct_this))
					obj_coll.insert_one(dct_ins)

	except Exception as e:
		pass

	return lst_t10


def get_token_holdings(str_wadd):
	lst_ret = []
	str_url = 'https://api.ethplorer.io/getAddressInfo/%s?apiKey=freekey' % str_wadd
	obj_response = requests.get(str_url)
	if obj_response.status_code == 200:
		obj_json = obj_response.json()
		if 'tokens' in obj_json.keys():
			lst_ret = obj_json['tokens']

	return lst_ret;


def get_hb_score(str_wadd,lst_trans = [],dct_trans = {}):
	int_this_swing = 0
	int_this_max_swing = dct_score_index['0-historical_behavior']['weight'] * int_max_swing

	#compare previous score to current
	obj_client = MongoClient()
	obj_db = obj_client["lscores"]
	obj_coll = obj_db["lscores"]

	obj_doc = obj_db["lscores"].find({
		"address": str_wadd,
		"ts": {"$ne": dct_trans['ts']}
	}).sort('ts',-1).limit(2)

	if obj_doc.count() >= 2:
		dbl_pct = round(100 - ((obj_doc[0]['ledgerscore']/obj_doc[1]['ledgerscore']) * 100))
		
		#increases
		if dbl_pct > 50:
			int_this_swing = int_this_max_swing
		elif dbl_pct > 40 and dbl_pct <= 50:
			int_this_swing = (int_this_max_swing * .8)
		elif dbl_pct > 30 and dbl_pct <= 40:
			int_this_swing = (int_this_max_swing * .6)
		elif dbl_pct > 20 and dbl_pct <= 30:
			int_this_swing = (int_this_max_swing * .4)
		elif dbl_pct >= 10 and dbl_pct <= 20:
			int_this_swing = (int_this_max_swing * .2)

		#decreases	
		elif dbl_pct < -50:
			int_this_swing = 0
		elif dbl_pct >= -50 and dbl_pct < -40:
			int_this_swing = int_this_max_swing - (int_this_max_swing * .8)
		elif dbl_pct >= -40 and dbl_pct < -30:
			int_this_swing = int_this_max_swing - (int_this_max_swing * .6)
		elif dbl_pct >= -40 and dbl_pct < -30:
			int_this_swing = int_this_max_swing - (int_this_max_swing * .4)
		elif dbl_pct >= -30 and dbl_pct < -20:
			int_this_swing = int_this_max_swing - (int_this_max_swing * .2)

	dct_ret = { 'int_swing' : int_this_swing, 'lst_trans' : lst_trans }
	
	return dct_ret


def get_pref_tokens_score(str_wadd,lst_trans,dct_ret):
	int_this_swing = 0
	int_this_max_swing = dct_score_index['1-preferred_tokens']['weight'] * int_max_swing

	#get current top 10 defi tokens by market cap
	lst_tt = get_t10_defi_tokens()
	#get token holdings from add
	lst_mt = get_token_holdings(str_wadd)

	lst_tt_2 = [str_LED_add]
	for dct_tt in lst_tt:
		lst_tt_2.append(dct_tt['address'])

	dbl_token_bal = 0.00
	dbl_ptoken_bal = 0.00
	for dct_mt in lst_mt:
		dbl_token_bal += dct_mt['balance']
		if dct_mt['tokenInfo']['address'] in lst_tt_2:
			dbl_ptoken_bal += dct_mt['balance']

	#calc pct
	if dbl_token_bal > 0 and dbl_ptoken_bal > 0:
		dbl_m_tb = move_point(float(dbl_token_bal),-18)
		dbl_m_ptb = move_point(float(dbl_ptoken_bal),-18)
		dbl_pct = get_percent(dbl_m_ptb, dbl_m_tb)
		
		#increases
		if dbl_pct > 50:
			int_this_swing = int_this_max_swing
		elif dbl_pct > 40 and dbl_pct <= 50:
			int_this_swing = (int_this_max_swing * .8)
		elif dbl_pct > 30 and dbl_pct <= 40:
			int_this_swing = (int_this_max_swing * .6)
		elif dbl_pct > 20 and dbl_pct <= 30:
			int_this_swing = (int_this_max_swing * .4)
		elif dbl_pct >= 10 and dbl_pct <= 20:
			int_this_swing = (int_this_max_swing * .2)		
	
	if len(lst_mt) > 0:
		obj_client = MongoClient()
		obj_db = obj_client["lscores_tokenholdings"]
		obj_coll = obj_db["lscores_tokenholdings"]
		dbl_ts = datetime.datetime.now().timestamp()
		dct_this = {'address' : str_wadd, 'lst_tt' : lst_tt, 'lst_mt' : lst_mt, 'ts': dbl_ts}
		dct_ins = json.loads(json_util.dumps(dct_this))
		obj_coll.insert_one(dct_ins)


	dct_ret = { 'int_swing' : int_this_swing, 'lst_trans' : lst_trans }
	
	return dct_ret


def get_lsrank_score(str_wadd,lst_trans,dct_trans):
	int_this_swing = 0
	int_this_max_swing = dct_score_index['2-get_lsrank_score']['weight'] * int_max_swing

	#get current avg
	int_avg = 0
	obj_client = MongoClient()
	obj_db = obj_client["lscores"]
	obj_coll = obj_db["lscores"]

	#get 
	obj_ls = obj_coll.find({ 'address' : str_wadd },{'_id': False}).sort('ts',-1).limit(1)
	if obj_ls.count() > 0:
		
		obj_avg = obj_coll.aggregate([{ "$group": { "_id" : None, "ls" : {"$avg" : "$ledgerscore"} } }])
		for obj_i in obj_avg:
			int_avg = obj_i['ls']

		dbl_pct = get_percent(int_avg,obj_ls[0]['ledgerscore']) if int_avg > 0 else 0	
			
		if dbl_pct >= 10:
			int_this_swing = int_this_max_swing
		elif dbl_pct >= 8 and dbl_pct < 10:
			int_this_swing = (int_this_max_swing * .8)
		elif dbl_pct >= 6 and dbl_pct < 8:
			int_this_swing = (int_this_max_swing * .6)
		elif dbl_pct >= 4 and dbl_pct < 6:
			int_this_swing = (int_this_max_swing * .4)
		elif dbl_pct >= 2 and dbl_pct < 4:
			int_this_swing = (int_this_max_swing * .2)


	dct_ret = { 'int_swing' : int_this_swing, 'lst_trans' : lst_trans }
	
	return dct_ret


def get_trans_score(str_wadd,lst_trans = [],dct_trans = {}):
	int_this_swing = 0
	int_this_max_swing = dct_score_index['3-get_trans_score']['weight'] * int_max_swing
	
	if len(dct_trans.keys()) > 0:
		if dct_trans['eth_balance'] > 0:

			dbl_recvd = move_point(float(dct_trans['eth_received']),-18)
			dbl_sent = move_point(float(dct_trans['eth_sent']),-18)
			dbl_tot_mov = move_point(float(dct_trans['eth_received']) + float(dct_trans['eth_sent']),-18)
			
			dbl_pct_recvd = (dbl_recvd / dbl_tot_mov) if dbl_tot_mov > 0 else 0
			dbl_pct_sent = (dbl_sent / dbl_tot_mov) if dbl_tot_mov > 0 else 0

			#recvd
			if (dbl_pct_recvd) >= .5:
				int_this_swing = int_this_max_swing
			elif (dbl_pct_recvd) >= .4:
				int_this_swing = (int_this_max_swing * .8)
			elif (dbl_pct_recvd) >= .3:
				int_this_swing = (int_this_max_swing * .6)
			elif (dbl_pct_recvd) >= .2:
				int_this_swing = (int_this_max_swing * .4)

			#sends
			if int_this_swing > 0 and (dbl_pct_sent) >= .5:
				int_this_swing - int_this_max_swing
			elif int_this_swing > 0 and (dbl_pct_sent) >= .4:
				int_this_swing -= (int_this_max_swing * .8)
			elif int_this_swing > 0 and (dbl_pct_sent) >= .3:
				int_this_swing -= (int_this_max_swing * .6)
			elif int_this_swing > 0 and (dbl_pct_sent) >= .2:
				int_this_swing -= (int_this_max_swing * .4)

			if int_this_swing < 0:
				int_this_swing = 0
			if int_this_swing > int_this_max_swing:
				int_this_swing = int_this_max_swing

	dct_ret = { 'int_swing' : int_this_swing, 'lst_trans' : lst_trans }
	
	return dct_ret

def get_ls_score(str_wadd,dbl_ts,lst_trans = [],dct_ret = {}):
	int_ret_score = int_min_score
	int_this_swing = 0
	dct_det_score = {}
	for str_key in sorted(dct_score_index.keys()):
		lst_key = str_key.split('-')
		if(lst_key[1] == 'historical_behavior'):
			dct_swing = get_hb_score(str_wadd,lst_trans,dct_ret)
			int_this_swing += dct_swing['int_swing']
			dct_det_score[lst_key[1]] = int_this_swing
			#print(dct_swing['int_swing'], ' HB!!!')
		elif(lst_key[1] == 'get_trans_score'):
			dct_swing = get_trans_score(str_wadd,lst_trans,dct_ret)
			int_this_swing += dct_swing['int_swing']
			dct_det_score[lst_key[1]] = int_this_swing
			#print(dct_swing['int_swing'], ' TRANS!!!')
		elif(lst_key[1] == 'get_lsrank_score'):
			dct_swing = get_lsrank_score(str_wadd,lst_trans,dct_ret)
			int_this_swing += dct_swing['int_swing']
			dct_det_score[lst_key[1]] = int_this_swing
			#print(dct_swing['int_swing'], ' LSRANK!!!')
		elif(lst_key[1] == 'preferred_tokens'):
			dct_swing = get_pref_tokens_score(str_wadd,lst_trans,dct_ret)
			int_this_swing += dct_swing['int_swing']
			dct_det_score[lst_key[1]] = int_this_swing
			#print(dct_swing['int_swing'], ' PREFTOK!!!')
		
	int_ret_score += int_this_swing

	if int_ret_score > int_max_swing:
		int_ret_score = int_max_swing
	elif int_ret_score < int_min_score:
		int_ret_score = int_min_score

	#details for score
	lst_lsd = set_ls_score_detail(str_wadd,lst_trans,dct_ret,dct_det_score,int_ret_score,dbl_ts)
	if len(lst_lsd) > 0:
		obj_client = MongoClient()
		obj_db = obj_client["lscores_details"]
		obj_coll = obj_db["lscores_details"]
		dbl_ts = datetime.datetime.now().timestamp()
		dct_this = {'address' : str_wadd, 'ts': dbl_ts, 'lst_lsd' : lst_lsd}
		dct_ins = json.loads(json_util.dumps(dct_this))
		obj_coll.insert_one(dct_ins)
		
	return int_ret_score

def set_ls_score_detail(str_wadd,lst_trans,dct_ret,dct_det_score,int_lscore,dbl_ts):

	lst_ret = []
	lst_status = ['negative','neutral','positive']
	int_score = 0

	#iterate in order
	if('historical_behavior' in dct_det_score.keys()):
		dct_thb = {
			'status' : lst_status[1],
			'dateTime' : dbl_ts,
			'address' : str_wadd,
			'value' : 0,
			'change' : 0,
			'score' : 0,
			'reason' : None
		}
		int_score = dct_det_score['historical_behavior']
		if dct_det_score['historical_behavior'] > 0:
			dct_thb['status'] = lst_status[2]
			dct_thb['change'] = dct_det_score['historical_behavior']
			dct_thb['score'] = dct_det_score['historical_behavior']
		dct_thb['reason'] = 'Historical Behavior'
		lst_ret.append(dct_thb)


	if('get_lsrank_score' in dct_det_score.keys()):
		dct_lsr = {
			'status' : lst_status[1],
			'dateTime' : dbl_ts,
			'address' : str_wadd,
			'value' : 0,
			'change' : 0,
			'score' : 0,
			'reason' : None
		}
		int_score += dct_det_score['get_lsrank_score']
		if dct_det_score['get_lsrank_score'] > 0:
			dct_lsr['status'] = lst_status[2]
			dct_lsr['change'] = dct_det_score['get_lsrank_score']
			dct_lsr['score'] = int_score
		dct_lsr['reason'] = 'LS Rank'
		lst_ret.append(dct_lsr)

	if('preferred_tokens' in dct_det_score.keys()):
		dct_pt = {
			'status' : lst_status[1],
			'dateTime' : dbl_ts,
			'address' : str_wadd,
			'value' : 0,
			'change' : 0,
			'score' : 0,
			'reason' : None
		}
		int_score += dct_det_score['preferred_tokens']
		if dct_det_score['preferred_tokens'] > 0:
			dct_pt['status'] = lst_status[2]
			dct_pt['change'] = dct_det_score['preferred_tokens']
			dct_pt['score'] = int_score
		dct_pt['reason'] = 'Preferred Tokens'
		lst_ret.append(dct_pt)

	
	if('get_trans_score' in dct_det_score.keys()):
		
		int_this_max_swing = dct_score_index['3-get_trans_score']['weight'] * int_max_swing

		if dct_ret['eth_balance'] > 0:
			dbl_tot_mov = dct_ret['eth_received'] + dct_ret['eth_sent']
			

			dbl_pct_recvd = 0
			dbl_pct_sent = 0
			
			for dct_trans in lst_trans:

				dbl_val = move_point(float(dct_trans['value']),-18)
				dct_t = {
					'status' : lst_status[1],
					'dateTime' : dct_trans['timeStamp'],
					'address' : str_wadd,
					'value' : dbl_val,
					'change' : 0,
					'score' : int_score,
					'reason' : 'Transaction'
				}

				#received
				if dct_trans['to'].upper() == str_wadd.upper() and dbl_val > 0:
					#get pct of this # of total mov
					dbl_this_pct = (dbl_val / dbl_tot_mov) if dbl_tot_mov > 0 else 0
					dbl_pct_recvd_b = dbl_pct_recvd
					dbl_pct_recvd += dbl_this_pct

					if (dbl_pct_recvd) >= .5 and dbl_pct_recvd_b < .5:
						dct_t['status'] = lst_status[2]
						dct_t['change'] = int_this_max_swing
						dct_t['score'] = int_score + int_this_max_swing
					elif (dbl_pct_recvd) >= .4 and dbl_pct_recvd_b < .4:
						dct_t['status'] = lst_status[2]
						dct_t['change'] = int_this_max_swing * .8
						dct_t['score'] = int_score + (int_this_max_swing * .8)
					elif (dbl_pct_recvd) >= .3 and dbl_pct_recvd_b < .3:
						dct_t['status'] = lst_status[2]
						dct_t['change'] = int_this_max_swing * .6
						dct_t['score'] = int_score + (int_this_max_swing * .6)
					elif (dbl_pct_recvd) >= .2 and dbl_pct_recvd_b < .2:
						dct_t['status'] = lst_status[2]
						dct_t['change'] = int_this_max_swing * .4
						dct_t['score'] = int_score + (int_this_max_swing * .4)

				#sent
				if dct_trans['to'].upper() != str_wadd.upper() and dbl_val > 0:
					#get pct of this # of total mov
					dbl_this_pct = (dbl_val / dbl_tot_mov) if dbl_tot_mov > 0 else 0
					dbl_pct_sent_b = dbl_pct_sent
					dbl_pct_sent += dbl_this_pct

					if (dbl_pct_sent) >= .5 and dbl_pct_recvd_b < .5:
						dct_t['status'] = lst_status[0]
						dct_t['change'] = -(int_this_max_swing) if ((int_score - int_this_max_swing) >= int_score) else -(int_this_max_swing - int_score)
						dct_t['score'] = (int_score - int_this_max_swing) if ((int_score - int_this_max_swing) >= int_score) else int_score
					elif (dbl_pct_sent) >= .4 and dbl_pct_sent_b < .4:
						dct_t['status'] = lst_status[0]
						dct_t['change'] = -(int_this_max_swing * .8) if ((int_score - int_this_max_swing * .8) >= int_score) else -(int_this_max_swing * .8 - int_score)
						dct_t['score'] = (int_score - int_this_max_swing * .8) if ((int_score - int_this_max_swing * .8) >= int_score) else int_score
					elif (dbl_pct_sent) >= .3 and dbl_pct_sent_b < .3:
						dct_t['status'] = lst_status[0]
						dct_t['change'] = -(int_this_max_swing * .6) if ((int_score - int_this_max_swing * .6) >= int_score) else -(int_this_max_swing * .6 - int_score)
						dct_t['score'] = (int_score - int_this_max_swing * .6) if ((int_score - int_this_max_swing * .6) >= int_score) else int_score
					elif (dbl_pct_recvd) >= .2 and dbl_pct_recvd_b < .2:
						dct_t['status'] = lst_status[0]
						dct_t['change'] = -(int_this_max_swing * .4) if ((int_score - int_this_max_swing * .4) >= int_score) else -(int_this_max_swing * .8 - int_score)
						dct_t['score'] = (int_score - int_this_max_swing * .4) if ((int_score - int_this_max_swing * .4) >= int_score) else int_score

				lst_ret.append(dct_t)


	return lst_ret

def get_wallet_obj(str_wadd):
	#dct_json_data = request.get_json()
	dct_ret = { "address" : str_wadd }
	##str_url = 'https://api-ropsten.etherscan.io/api?module=account&action=txlist&address=%s&sort=asc&apikey=%s' % (str_wadd,str_api_key)
	str_url = 'https://api.etherscan.io/api?module=account&action=txlist&address=%s&sort=asc&apikey=%s' % (str_wadd,str_api_key)
	obj_headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.1 Safari/537.36'}
	dbl_ts = datetime.datetime.now().timestamp()

	obj_response = requests.get(str_url,headers=obj_headers)
	if obj_response.status_code == 200:
		obj_json = obj_response.json()

		#1st determine if last record of trans pull == last record of stored json obj
		#next determine ts of last calc to determine if re-calc is needed
		#if exists return saved obj
		#else calculate new score
		obj_client = MongoClient()
		obj_db = obj_client["lscores"]
		obj_coll = obj_db["lscores"]

		is_ret_rec = False
		obj_lrec = obj_coll.find({ 'address' : str_wadd },{'_id': False}).sort('ts',-1).limit(1)
		if obj_lrec.count() > 0 and len(obj_json['result']) > 0:
			for obj_r in obj_json['result'][::-1]:
				if obj_r['isError'] == '0':
					#if obj_lrec[0]['last_hash'] == obj_r['hash']:
					dat_td = datetime.datetime.fromtimestamp(dbl_ts)
					dat_td_m = datetime.datetime.fromtimestamp(obj_lrec[0]['ts'])
					dat_dur = dat_td - dat_td_m
					#10 mins
					if dat_dur.total_seconds() <= 5: #86400:
						is_ret_rec = True
					break

		if is_ret_rec == True:
			dct_ret = obj_lrec[0]
		else:
			int_bal_changes = 0
			dbl_tot_bc_or = 0.00
			dbl_tot_bc = 0.00
			dbl_eth_rcvd = 0.00
			dbl_eth_sent = 0.00
			int_tx_sent = 0
			int_tx_rcvd = 0
			int_gas_used_in_wei = 0
			is_1st = False
			lst_trans = []
			str_last_hash = None
			for dct_this in obj_json['result']:
				#int_bal_changes
				if int(dct_this['value']) != 0: 
					int_bal_changes += 1

				#dbl_tot_bc
				if dct_this['isError'] == "0" and not is_1st:
					is_1st = True
					#dbl_this = float(dct_this['value'])
					#dbl_this /= 1000000000000000000.
					dbl_tot_bc_or = move_point(float(dct_this['value']),-18)
					str_last_hash = dct_this['hash']
				elif dct_this['isError'] == "0":
					#dbl_this = float(dct_this['value'])
					#dbl_this /= 1000000000000000000.
					dbl_tot_bc += abs( move_point(float(dct_this['value']),-18))
					str_last_hash = dct_this['hash']
				#dbl_eth_rcvd
				if dct_this['to'].upper() == str_wadd.upper() and dct_this['isError'] == "0":
					dbl_eth_rcvd += move_point(float(dct_this['value']),-18)
					int_tx_rcvd += 1
				elif dct_this['to'].upper() != str_wadd.upper() and dct_this['isError'] == "0":
					dbl_eth_sent += move_point(float(dct_this['value']),-18)
					int_tx_sent += 1
				#gas_used_in_wei
				int_gas_used_in_wei += int(dct_this['gasUsed'])
				
				lst_trans.append(dct_this)

			#int_total
			dbl_eth_bal = 0.00 
			str_url = 'https://api.etherscan.io/api?module=account&action=balance&address=%s&tag=latest&apikey=%s' % (str_wadd,str_api_key)
			obj_response_2 = requests.get(str_url,headers=obj_headers)
			if obj_response_2.status_code == 200:
				obj_json_2 = obj_response_2.json()
				dbl_eth_bal = move_point(float(obj_json_2['result']),0)

			del obj_response_2


			dct_ret['eth_balance'] = dbl_eth_bal
			dct_ret['times_balance_changed'] = int_bal_changes
			dct_ret['total_balance_change'] = dbl_tot_bc
			dct_ret['eth_received'] = dbl_eth_rcvd
			dct_ret['eth_sent'] = dbl_eth_sent
			dct_ret['gas_used_in_wei'] = int_gas_used_in_wei
			dct_ret['tx_received'] = int_tx_rcvd
			dct_ret['tx_sent'] = int_tx_sent
			dct_ret['avg_sent_tx_value'] = dbl_eth_sent / int_tx_sent if int_tx_sent > 0 else 0
			dct_ret['avg_received_tx_value'] = dbl_eth_rcvd / int_tx_rcvd if int_tx_rcvd > 0 else 0
			#todo: get verification status from last_pmt
			dct_ret['verified'] = False
			dct_ret['ts'] = dbl_ts
			dct_ret['last_hash'] = str_last_hash
			
			#we only calculate score in real-time on init
			dct_ret['ledgerscore'] = get_ls_score(str_wadd,dbl_ts,lst_trans,dct_ret)
	
			dct_ins = json.loads(json_util.dumps(dct_ret))
			obj_coll.insert_one(dct_ins)

	return dct_ret

def get_wallet_objs(str_wadd,dat_b,dat_e):
	#dct_json_data = request.get_json()
	dct_ret = { "address" : str_wadd, "dates": {} }
	
	#parse dates
	dat_b2 = None
	dat_e2 = None
	try:
		dat_b2 = datetime.datetime.strptime(dat_b, '%Y-%m-%d')
		dat_e2 = datetime.datetime.strptime(dat_e, '%Y-%m-%d')
	except Exception as e:
		pass

	if dat_b2 is not None and dat_e2 is not None and dat_e2 > dat_b2:
		obj_client = MongoClient()
		obj_db = obj_client["lscores"]
		obj_coll = obj_db["lscores"]
		
		dat_b3 = dat_b2
		obj_delta = datetime.timedelta(days=1)
		while dat_b3 < dat_e2:
			
			obj_lrec = obj_coll.find({ "$and" : [{'address' : str_wadd},{'ts' : { "$gte" : dat_b3.timestamp() }},{'ts' : { "$lt" : dat_b3.timestamp() + 86400 }}] },{'_id': False}).sort('ts',-1).limit(1)
			dct_ret['dates'][dat_b3.strftime('%Y-%m-%d')] = None
			for dct_lrec in obj_lrec:
				dct_ret['dates'][dat_b3.strftime('%Y-%m-%d')] = dct_lrec
			dat_b3 += obj_delta

	return dct_ret



def get_wallet_det_objs(str_wadd,dat_b,dat_e):
	#dct_json_data = request.get_json()
	lst_ret = []
	
	#parse dates
	dat_b2 = None
	dat_e2 = None
	try:
		dat_b2 = dat_b
		dat_e2 = dat_e
	except Exception as e:
		pass

	if dat_b2 is not None and dat_e2 is not None and dat_e2 > dat_b2:
		obj_client = MongoClient()
		obj_db = obj_client["lscores_details"]
		obj_coll = obj_db["lscores_details"]
		
		dat_b3 = dat_b2
		##obj_delta = datetime.timedelta(days=1)
		while dat_b3 < dat_e2:
			
			obj_lrec = obj_coll.find({ "$and" : [{'address' : str_wadd},{'ts' : { "$gte" : dat_b3 }},{'ts' : { "$lt" : dat_b3 + 86400 }}] },{'_id': False}).sort('ts',-1).limit(1)
			#dct_ret['dates'][dat_b3.strftime('%Y-%m-%d')] = None
			for dct_lrec in obj_lrec:
				lst_ret += dct_lrec['lst_lsd']
			dat_b3 += 86400

	return lst_ret