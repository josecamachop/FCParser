#!/usr/bin/env python

"""
parser -- Program for parsing and processing raw network
data and preparing it for further multivariate analysis using
FaaC parser library.


Authors:    Jose Camacho (josecamacho@ugr.es)
	    Jose Manuel Garcia Gimenez (jgarciag@ugr.es) 
	    Alejandro Perez Villegas (alextoni@gmail.com)
		 
		 
Last Modification: 16/Jul/2018

"""

from collections import OrderedDict
import argparse
import glob
import datetime
import os
import gzip
import re
import time
import shutil
import yaml
import subprocess
from operator import add
import faac
	
def main(call='external',configfile=''):

	startTime = time.time()

	# if called from terminal
	# if not, the parser must be called in this way: parser.main(call='internal',configfile='<route_to_config_file>')
	if call is 'external':
		args = getArguments()
		configfile = args.config

	# Get configuration
	parserConfig = faac.getConfiguration(configfile)
	dataSources = parserConfig['DataSources']
	output = parserConfig['Output']
	config = faac.loadConfig(output, dataSources, parserConfig)

	# Print configuration summary
	configSummary(config)

	# Count data entries
	stats = create_stats(config)
	stats = count_entries(config,stats) 

	# Parse
	output_data = parsing(config, startTime)

	# Filter output
	output_data = filter_output(output_data, stats['total_lines']*0.01)

	# Output results
	write_output(config, output_data, stats['total_lines']*0.01)
			

	print "Elapsed: %s \n" %(prettyTime(time.time() - startTime))	


def parsing(config,startTime):
	'''
	Main process for parsing. The program is in charge of temporal sampling.
	'''
	results = {}
	final_res = {}

	for source in config['SOURCES']:


		results[source] = []
		currentTime = time.time()
		print "\n-----------------------------------------------------------------------\n"
		print "Elapsed: %s \n" %(prettyTime(currentTime - startTime))	


		results[source] = process_multifile(config, source)


	return results

def process_multifile(config, source):
	'''
	processing files procedure for unstructured sources in offline parsing. In this function the pool 
	of proccesses is created. Each file is fragmented in chunk sizes that can be load to memory. 
	Each process is assigned a chunk of file to be processed.
	The results of each process are gathered to be postprocessed. 
	'''
	instances = {}
	for variable in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
		instances[config['SOURCES'][source]['CONFIG']['VARIABLES'][variable]['name']] = {}

	count = 0

	for i in range(len(config['SOURCES'][source]['FILES'])):
		input_path = config['SOURCES'][source]['FILES'][i]
		if input_path:
			count += 1
			tag = getTag(input_path)

			#Print some progress stats
			print "%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILES'])), tag)	
		
			instances = process_file(input_path,config,source,config['SEPARATOR'][source],instances)

	return instances




def process_file(file, config, source,separator,instances):
	'''
	Function that uses each process to get data entries from unstructured data using the separator defined
	in configuration files that will be transformed into observations. This is used only in offline parsing. 
	'''
	try:
	
		if file.endswith('.gz'):					
			f = gzip.open(file, 'r')
		else:
			f = open(file, 'r')

		log = ''
		for line in f:
			log += line 

			if separator in log:
				instances = process_log(log,config, source, instances)
				log = log.split(separator)[1]
		if log:	
			instances = process_log(log,config, source, instances)

	finally:
		f.close()
	
	return instances


def process_log(log, config, source, instances):
	'''
	Function take on data entry as input an transform it into a preliminary observation
	'''	 

	record = faac.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source])

	for key,value in record.variables.items():
		if key != 'timestamp':
			if str(value) in instances[key]:
				instances[key][str(value)] += 1
			else:
				instances[key][str(value)] = 1	

	return instances
	
def normalize_timestamps(timestamp, config, source):
	'''
	Function that transform timestamps of data entries to a normalized format. It also do the 
	time sampling using the time window defined in the configuration file.
	'''	
	try:
		input_format = config['SOURCES'][source]['CONFIG']['timestamp_format']
		window = config['Time']['window']
		t = datetime.datetime.strptime(str(timestamp), input_format)
		new_minute = t.minute - t.minute % window  
		t = t.replace(minute = new_minute, second = 0)	


		if t.year == 1900:
			t = t.replace(year = datetime.datetime.now().year)
		return t
	except:
		
		return 0



def create_stats(config):
	'''
	Legacy function - To be updated
	'''
	stats = {}
	statsPath = config['OUTDIR'] + config['OUTSTATS']
	statsStream = open(statsPath, 'w')
	statsStream.write("STATS\n")
	statsStream.write("=================================================\n\n")
	statsStream.close()
	stats['statsPath'] = statsPath

	return stats

def count_entries(config,stats):
	'''
	Function to get the amount of data entries for each data source
	TO BE UPDATED
	'''
	lines = {}
	for source in config['SOURCES']:
		lines[source] = 0
		
		for file in config['SOURCES'][source]['FILES']:
			if config['STRUCTURED'][source]:
				lines[source] += file_len(file)

			else:
				lines[source] += file_uns_len(file,config['SEPARATOR'][source])
	
	# Sum lines from all datasources to obtain tota lines.
	total_lines = 0

	stats['lines'] = {}
	for source in lines:
		total_lines += lines[source]
		stats['lines'][source] = lines[source]

	stats['total_lines'] = total_lines

	return stats

def configSummary(config):
	'''
	Print a summary of loaded parameters
	'''

	print "-----------------------------------------------------------------------"
	print "Data Sources:"
	for source in config['SOURCES']:
		print " * %s %s variables " %((source).ljust(18), str(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])).ljust(2))
	print
	print "Output:"
	print "  Stats file: %s" %(config['OUTSTATS'])
	print "-----------------------------------------------------------------------\n"
	


def getTag(filename):
	'''
	function to identify data source by the input file
	'''
	tagSearch = re.search("(\w*)\.\w*$", filename)
	if tagSearch:
		return tagSearch.group(1)
	else:
		return None

def file_uns_len(fname, separator):
	'''
	Function determine de number of logs for a unstructured file 
	'''
	if fname.endswith('.gz'):
		input_file = gzip.open(fname,'r')
	else:
		input_file = open(fname,'r')

	line = input_file.readline()
	count_log = 0

	if line:
		log ="" + line

		while line:
			log += line 

			if len(log.split(separator)) > 1:
				logExtract = log.split(separator)[0]
				count_log += 1		
				log = ""

				for n in logExtract.split(separator)[1::]:
					log += n

			line = input_file.readline()
		log += line
		
		if not log == "":
			count_log += 1 

	return count_log			
	
def prettyTime(elapsed):
	'''
	Function to format time for print.
	'''
	hours = int(elapsed // 3600)
	minutes = int(elapsed // 60 % 60)
	seconds = int(elapsed % 60)
	pretty = str(seconds) + " secs"
	if minutes or hours:
		pretty = str(minutes) + " mins, " + pretty
	if hours:
		pretty = str(hours) + " hours, " + pretty
	return pretty


def file_len(fname):
	'''
	Function to get lines from a file
	'''
	with open(fname) as f:
		for i, l in enumerate(f):
			pass
	return i + 1

def getArguments():
	'''
	Function to get input arguments from configuration file
	'''
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Multivariate Analysis Parsing Tool.''')
	parser.add_argument('config', metavar='CONFIG', help='Parser Configuration File.')
	args = parser.parse_args()
	return args


def filter_output(output_data,threshold):
	'''Filter de data to only common fatures
	'''

	for source in output_data.keys():
		for varkey in output_data[source].keys():
			for feakey in output_data[source][varkey].keys():
				if output_data[source][varkey][feakey] < threshold:
					del output_data[source][varkey][feakey]

	return output_data
					

def write_output(config, output_data, threshold):
	'''Write configuration file
	'''

	contentf = dict()
	contentf['FEATURES'] = list()

	yaml.add_representer(UnsortableOrderedDict, yaml.representer.SafeRepresenter.represent_dict)

	for source in output_data.keys():
		print "\nWriting configuration file " + config['SOURCES'][source]['CONFILE'] + "\n" 
		for varkey in output_data[source].keys():
			for feakey in output_data[source][varkey].keys():
				interm = UnsortableOrderedDict()
				interm['name'] = source + '_' + varkey + '_' + feakey.replace(" ", "")
				interm['variable'] = varkey
				interm['matchtype'] = 'regexp'
				interm['value'] = feakey
				interm['weight'] = output_data[source][varkey][feakey]/threshold
				contentf['FEATURES'].append(interm)

		for i in range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
			vType = config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['matchtype']
			vName = config['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name']

			if vName != 'timestamp':
				if vType == 'string':
					interm = UnsortableOrderedDict()
					interm['name'] = source + '_' + vName + '_default'
					interm['variable'] = vName
					interm['matchtype'] = 'default'
					interm['value'] = ''
					interm['weight'] = 1
					contentf['FEATURES'].append(interm)
				elif vType == 'number':
					interm = UnsortableOrderedDict()
					interm['name'] = source + '_' + vName + '_default'
					interm['variable'] = vName
					interm['matchtype'] = 'default'
					interm['value'] = ''
					interm['weight'] = 1
					contentf['FEATURES'].append(interm)
				elif vType == 'ip':
					interm = UnsortableOrderedDict()
					interm['name'] = source + '_' + vName + '_private'
					interm['variable'] = vName
					interm['matchtype'] = 'single'
					interm['value'] = 'private'
					interm['weight'] = 1
					contentf['FEATURES'].append(interm)

					interm = UnsortableOrderedDict()
					interm['name'] = source + '_' + vName + '_public'
					interm['variable'] = vName
					interm['matchtype'] = 'single'
					interm['value'] = 'public'
					interm['weight'] = 1
					contentf['FEATURES'].append(interm)

		# write resuls in yaml
		try:
			f = file(config['SOURCES'][source]['CONFILE'], 'a')
			f.write('\n\n')
			yaml.dump(contentf, f, default_flow_style=False)
		except:
	    		print "Problem writing " + yamlfile
	    		quit()
		finally:
			f.close()

	

class UnsortableList(list):
    def sort(self, *args, **kwargs):
        pass

class UnsortableOrderedDict(OrderedDict):
    def items(self, *args, **kwargs):
        return UnsortableList(OrderedDict.items(self, *args, **kwargs))


if __name__ == "__main__":
	
	main()
