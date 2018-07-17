#!/usr/bin/env python

"""
parser -- Program for parsing and processing raw network
data and preparing it for further multivariate analysis using
FaaC parser library.


Authors:    Jose Manuel Garcia Gimenez (jgarciag@ugr.es) 
			Alejandro Perez Villegas (alextoni@gmail.com)
		 
		 
Last Modification: 14/May/2018

"""

import multiprocessing as mp
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
import faaclib
	
def main(call='external',configfile=''):

	startTime = time.time()

	# if called from terminal
	# if not, the parser must be called in this way: parser.main(call='internal',configfile='<route_to_config_file>')
	if call is 'external':
		args = getArguments()
		configfile = args.config

	# Get configuration
	parserConfig = getConfiguration(configfile)
	online = parserConfig['Online']
	dataSources = parserConfig['DataSources']
	output = parserConfig['Output']
	config = loadConfig(output, dataSources, parserConfig)

	# Print configuration summary
	configSummary(config)

	# Output Weights
	outputWeight(config)
	stats = create_stats(config)

	# Count data entries
	stats = count_entries(config,stats) 

	# processing files
	if online:
		data = online_parsing(config)
		output_data,headers = fuseObs_online(data, config)

	# process offline 
	else:
		data = offline_parsing(config, startTime)
		output_data,headers = fuseObs_offline(data, config)

	# Output results
	write_output(output_data, headers, config)

	print "Elapsed: %s \n" %(prettyTime(time.time() - startTime))	

def online_parsing(config):
	'''
	Main process for online parsing. In this case, the program generates one output for the 
	the input file, wich means, no time splitting. Online parsing is designed to be integrated
	in other program with would be in charge of the input management. 
	'''
	results = {}

	for source in config['SOURCES']:
		obsDict = obsDict_online()

		if config['SOURCES'][source]['CONFIG']['structured']:
			for fname in config['SOURCES'][source]['FILES']:
				if fname.endswith('.gz'):
					with gzip.open(fname, 'r') as f:
						lines = f.readlines()
						for line in lines:
							tag, obs = process_log(line,config, source)
							obsDict.add(obs)
				else:
					with open(fname, 'r') as f:
						lines = f.readlines()
						for line in lines:
							tag, obs = process_log(line,config, source)
							obsDict.add(obs)
		else:
			separator = config['SEPARATOR'][source]
			for fname in config['SOURCES'][source]['FILES']:
				if fname.endswith('.gz'):					
					with gzip.open(fname, 'r') as f:
						lines = f.read()
						log = ''
						for line in lines:
							log += line 
							if separator in log:
								tag, obs = process_log(log,config, source)
								obsDict.add(obs)
								log = ''	

						tag, obs = process_log(log,config, source)
						obsDict.add(obs)
				else: 
					with open(fname, 'r') as f:
						lines = f.read()
						log = ''
						for line in lines:
							log += line 
							if separator in log:
								tag, obs = process_log(log,config, source)
								obsDict.add(obs)
								log = ''	

						tag, obs = process_log(log,config, source)
						obsDict.add(obs)

		results[source] = obsDict
	return results

def offline_parsing(config,startTime):
	'''
	Main process for offline parsing. In this case, the program is in charge of temporal sampling.
	Also, it is multiprocess for processing large files faster. Number of cores used and chunk sizes
	to divide files for the different processes. 
	'''
	results = {}
	final_res = {}

	for source in config['SOURCES']:

		if config['SOURCES'][source]['CONFIG']['structured']:

			results[source] = []
			currentTime = time.time()
			print "\n-----------------------------------------------------------------------\n"
			print "Elapsed: %s \n" %(prettyTime(currentTime - startTime))	
			
			results[source] = process_str(config, source)

		else:
			results[source] = []
			currentTime = time.time()
			print "\n-----------------------------------------------------------------------\n"
			print "Elapsed: %s \n" %(prettyTime(currentTime - startTime))	
			
			results[source] = process_unstr(config, source)


	for source in results:
		final_res[source] = results[source][0].obsList
		for result in results[source][1:]:
			final_res[source] = combine_results(final_res[source], result.obsList)

	return final_res

def process_unstr(config, source):
	'''
	processing files procedure for unstructured sources in offline parsing. In this function the pool 
	of proccesses is created. Each file is fragmented in chunk sizes that can be load to memory. 
	Each process is assigned a chunk of file to be processed.
	The results of each process are gathered to be postprocessed. 
	'''
	results = []
	count = 0

	for i in range(len(config['SOURCES'][source]['FILES'])):
		pool = mp.Pool(config['Cores'])
		jobs = []
		input_path = config['SOURCES'][source]['FILES'][i]
		if input_path:
			count += 1
			tag = getTag(input_path)

			#Print some progress stats
			print "%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILES'])), tag)	
		

			for fragStart,fragSize in frag_unstr(input_path,config['SEPARATOR'][source], config['Csize']):
				jobs.append( pool.apply_async(process_wrapper_unstr,(input_path,fragStart,fragSize,config, source,config['SEPARATOR'][source])) )

			for job in jobs:
				results.append(job.get())

		pool.close()
	return results

def process_str(config, source):
	'''
	processing files procedure for structured sources in offline parsing. In this function the pool 
	of proccesses is created. Each file is fragmented in chunk sizes that can be load to memory. 
	Each process is assigned a chunk of file to be processed.
	The results of each process are gathered to be postprocessed. 
	'''
	results = []
	count = 0
	
	for i in range(len(config['SOURCES'][source]['FILES'])):
		jobs = []
		pool = mp.Pool(config['Cores'])
		input_path = config['SOURCES'][source]['FILES'][i]
		if input_path:
			count += 1
			tag = getTag(input_path)

			#Print some progress stats
			print "%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILES'])), tag)	

			for fragStart,fragSize in frag_str(input_path, config['Csize']):
				jobs.append( pool.apply_async(process_wrapper_str,(input_path,fragStart,fragSize,config, source)))

			for job in jobs:
				results.append(job.get())

		pool.close()
	return results
	
def fuseObs_offline(resultado, config):
	'''
	Function to fuse all the results obtained from all the processes to form a single matrix
	of observations with the information from all the input data. The program generated one observation
	for each time interval defined in the configuration file. 
	'''
	fused_res = {}
	features = []

	for source in resultado:

		for feat in config['SOURCES'][source]['CONFIG']['FEATURES']:
			features.append(feat['name'])

		arbitrary_len2 = len(next(iter(resultado[source].values())))
		try:
			arbitrary_len = len(next(iter(fused_res.values())))
		except:
			arbitrary_len = 0


		for date in resultado[source]:

			if date in fused_res:
				fused_res[date] = fused_res[date] + resultado[source][date] 
			else:
				fused_res[date] = [0]*arbitrary_len + resultado[source][date] 

		for date2 in fused_res:

			if date2 not in resultado[source]:
				fused_res[date2] = fused_res[date2] + [0]*arbitrary_len2

	return fused_res, features
	
def fuseObs_online(resultado, config):
	'''
	Function to fuse all the results obtained from all the processes to form a single observation in 
	array form.
	'''
	fused_res = []
	features = []

	for source in resultado:

		for feat in config['SOURCES'][source]['CONFIG']['FEATURES']:
			features.append(feat['name'])

		fused_res = fused_res + resultado[source].obsList

	return fused_res, features

def frag_unstr(fname,separator, size):
	'''
	Function to fragment files in chunks to be parallel processed for unstructured files
	'''
	fileEnd = os.path.getsize(fname)
	with open(fname, 'r') as f:
		end = f.tell()
		cont = True

		while True:
			start = end
			asdf = f.read(size)

			i = asdf.rfind(separator)

			if end >= fileEnd or i == -1:
				break

			f.seek(start+i+1)
			end = f.tell()
			yield start, end-start

def frag_str(fname, size):
	'''
	Function to fragment files in chunks to be parallel processed for structured files by lines
	'''
	separator = "\n"
	fileEnd = os.path.getsize(fname)
	if fname.endswith('.gz'):					
		with gzip.open(fname, 'r') as f:
			end = f.tell()
			cont = True
			while True:
				start = end
				asdf = f.read(size)
				i = asdf.rfind(separator)
				if end >= fileEnd or i == -1:
					break

				f.seek(start+i+1)
				end = f.tell()

				yield start, end-start
	else: 
		with open(fname, 'r') as f:
			end = f.tell()
			cont = True
			while True:
				start = end
				asdf = f.read(size)
				i = asdf.rfind(separator)
				if end >= fileEnd or i == -1:
					break

				f.seek(start+i+1)
				end = f.tell()

				yield start, end-start

def process_wrapper_unstr(file, fragStart, fragSize,config, source,separator):
	'''
	Function that uses each process to get data entries from unstructured data using the separator defined
	in configuration files that will be transformed into observations. This is used only in offline parsing. 
	'''
	obsDict = obsDict_offline()

	if file.endswith('.gz'):					
		with gzip.open(file, 'r') as f:
			f.seek(fragStart)
			lines = f.read(fragSize)

			log = ''
			for line in lines:
				log += line 

				if separator in log:
					tag, obs = process_log(log,config, source)
					obsDict.add(obs,tag)
					log = ''	

			tag, obs = process_log(log,config, source)
			obsDict.add(obs,tag)
	else:
		with open(file) as f:
			f.seek(fragStart)
			lines = f.read(fragSize)

			log = ''
			for line in lines:
				log += line 

				if separator in log:
					tag, obs = process_log(log,config, source)
					obsDict.add(obs,tag)
					log = log.split(separator)[1]	

			tag, obs = process_log(log,config, source)
			obsDict.add(obs,tag)
	return obsDict

def process_wrapper_str(file, fragStart, fragSize,config, source):
	'''
	Function that uses each process to get data entries from structured data lines.
	Lines will be transformed into observations. This is used only in offline parsing. 
	'''
	separator = "\n" 
	obsDict = obsDict_offline()

	if file.endswith('.gz'):					
		with gzip.open(file, 'r') as f:
			f.seek(fragStart)
			lines = f.read(fragSize).splitlines()
			for line in lines:
				tag, obs = process_log(line,config, source)
				obsDict.add(obs,tag)
	else:
		with open(file) as f:
			f.seek(fragStart)
			lines = f.read(fragSize).splitlines()
			for line in lines:
				tag, obs = process_log(line,config, source)
				obsDict.add(obs,tag)


	return obsDict

def process_log(log,config, source):
	'''
	Function take on data entry as input an transform it into a preliminary observation
	'''	 
	record = faaclib.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source])
	obs = faaclib.AggregatedObservation(record, config['FEATURES'][source], None)	

	return normalize_timestamps(record.variables['timestamp'],config, source), obs.data
	
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

def combine_results(dict1, dict2):
	'''
	Combine results of parsing from multiple process,
	Results are dicts with observations. The combination consist on 
	merging dicts, if a key is in both dicts, observations are added.
	'''
	dict3 = {}
	for key in dict1:
		if key in dict2:
			dict3[key] = map(add, dict1[key], dict2[key])
		else:
			dict3[key] = dict1[key]

	for key in dict2:
		if not (key in dict3):
			dict3[key] = dict2[key]

	return dict3

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

def outputWeight(config):
	'''
	Generate output file with the weights assigned to each feature.
	'''
	weightsPath = config['OUTDIR'] + config['OUTW']
	weightsStream = open(weightsPath, 'w')
	weightsStream.write(', '.join(config['features']) + '\n')
	weightsStream.write(', '.join(config['weigthts']) + '\n')
	weightsStream.close()

def configSummary(config):
	'''
	Print a summary of loaded parameters
	'''

	print "-----------------------------------------------------------------------"
	print "Data Sources:"
	for source in config['SOURCES']:
		print " * %s %s variables   %s features" %((source).ljust(18), str(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])).ljust(2), str(len(config['SOURCES'][source]['CONFIG']['FEATURES'])).ljust(3))
	print " TOTAL %s features" %(str(sum(len(l) for l in config['FEATURES'].itervalues())))
	print
	print "Output:"
	print "  Directory: %s" %(config['OUTDIR'])
	print "  Stats file: %s" %(config['OUTSTATS'])
	print "  Weights file: %s" %(config['OUTW'])
	print "-----------------------------------------------------------------------\n"
	
def loadConfig(output, dataSources, parserConfig):
	'''
	Function to load configuration from the config files
	'''
	Configuration = {}
	# Output settings 

	try:
		Configuration['OUTDIR'] = output['dir']
		if not Configuration['OUTDIR'].endswith('/'):
			Configuration['OUTDIR'] = Configuration['OUTDIR'] + '/'
	except (KeyError, TypeError):
		Configuration['OUTDIR'] = 'OUTPUT/'
		print " ** Default output directory: '%s'" %(Configuration['OUTDIR'])

	try:
		shutil.rmtree(Configuration['OUTDIR']+'/')
	except:
		pass

	if not os.path.exists(Configuration['OUTDIR']):
		os.mkdir(Configuration['OUTDIR'])
		print "** creating directory %s" %(Configuration['OUTDIR'])

	try:
		Configuration['OUTSTATS'] = output['stats']
	except (KeyError, TypeError):
		Configuration['OUTSTATS'] = 'stats.log'
		print " ** Default log file: '%s'" %(Configuration['OUTSTATS'])
	try:
		Configuration['OUTW'] = output['weights']
	except (KeyError, TypeError):
		# print " ** Default weights file: '%s'" %(Configuration['OUTW'])
		Configuration['OUTW'] = 'weights.dat'

	try: 
		Configuration['Time'] = parserConfig['SPLIT']['Time']

	except:
		print "**ERROR** Config file missing field: Time"
		exit(1)	

	try: 
		Configuration['Cores'] = int(parserConfig['Processes'])

	except:
		print "**ERROR** Config file missing field: Processes"
		exit(1)

	try: 
		Configuration['Csize'] = 1024 * int(parserConfig['Chunk_size'])

	except:
		print "**ERROR** Config file missing field: Chunk_size"
		exit(1)	

	# Sources settgins
	Configuration['SOURCES'] = {}
	for source in dataSources:
		Configuration['SOURCES'][source] = {}
		Configuration['SOURCES'][source]['CONFIG'] = getConfiguration(dataSources[source]['config'])
		Configuration['SOURCES'][source]['FILES'] = glob.glob(dataSources[source]['data'])

	Configuration['FEATURES'] = {}
	Configuration['STRUCTURED'] = {}
	Configuration['SEPARATOR'] = {}

	for source in Configuration['SOURCES']:
		Configuration['FEATURES'][source] = Configuration['SOURCES'][source]['CONFIG']['FEATURES']
		Configuration['STRUCTURED'][source] = Configuration['SOURCES'][source]['CONFIG']['structured']
		
		if not Configuration['STRUCTURED'][source]:
			Configuration['SEPARATOR'][source] = Configuration['SOURCES'][source]['CONFIG']['separator']	

			for i in range(len(Configuration['SOURCES'][source]['CONFIG']['VARIABLES'])):
				Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['r_Comp'] = re.compile(Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['where'])

			for i in range(len(Configuration['SOURCES'][source]['CONFIG']['FEATURES'])):
				if Configuration['SOURCES'][source]['CONFIG']['FEATURES'][i]['matchtype'] == 'regexp':
					Configuration['SOURCES'][source]['CONFIG']['FEATURES'][i]['r_Comp'] = re.compile(Configuration['SOURCES'][source]['CONFIG']['FEATURES'][i]['value'])



	# Preprocessing nfcapd files to obtain csv files.
	for source in dataSources:
		out_files = []
		for file in Configuration['SOURCES'][source]['FILES']:
			if 'nfcapd' in file:

				out_file = '/'.join(file.split('/')[:-1]) + '/temp_' + file.split('.')[-1] + ""
				os.system("nfdump -r " + file + " -o csv >>"+out_file)
				os.system('tail -n +2 '+out_file + '>>' + out_file.replace('temp',source))
				os.system('head -n -3 ' + out_file.replace('temp',source) + ' >> ' + out_file.replace('temp',source) + '.csv')
				out_files.append(out_file.replace('temp',source) + '.csv')
				os.remove(out_file)
				os.remove(out_file.replace('temp',source))
				Configuration['SOURCES'][source]['FILES'] = out_files
				delete_nfcsv = out_files

	# Process weight and made a list of features
	Configuration['features'] = []
	Configuration['weigthts'] = []

	for source in Configuration['FEATURES']:
		# Create weight file

		for feat in Configuration['SOURCES'][source]['CONFIG']['FEATURES']:
			try:	
				Configuration['features'].append(feat['name'])
			except:
				print "FEATURES: missing config key (%s)" %(e.message)
				exit(1)				
			try:
				Configuration['weigthts'].append(str(feat['weight']))
			except:
				Configuration['weigthts'].append('1')

	return Configuration

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

def getConfiguration(config_file):
	'''
	Function to load config file
	'''
	stream = file(config_file, 'r')
	conf = yaml.load(stream)
	stream.close()
	return conf

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

def write_output(output, headers, config):
	'''Write parsing ouput into a file, for each timestamp a file is written
	If the FCParser is mode online, only one file is written as output.
	Furthermore, an adition file with a list of the features is ouputted.
	'''

	with open(config['OUTDIR'] + 'headers.dat', 'w') as f:
		f.write(str(headers))

	if isinstance(output, dict):
		for k in output:
			try:
				tag = k.strftime("%Y%m%d%H%M")
			except:
				tag = str(k)

			with open(config['OUTDIR'] + 'output-'+ tag + '.dat' , 'w') as f:
				f.write(','.join(map(str,output[k])))
	else:
		with open(config['OUTDIR'] + 'output.dat' , 'w') as f:
			f.write(','.join(map(str,output)))

class obsDict_offline(object):
	"""
	Class to store observations of parsed data in offline mode. This class include 
	methods to add new partial observation to an absolute observation and a other 
	method for visual representation.
	"""
	def __init__(self):
		self.obsList = {}

	def add(self,obs,tag):
		if tag in self.obsList.keys():
			self.obsList[tag] = map(add, obs, self.obsList[tag])
		else:
			self.obsList[tag] = obs

	def printt(self):
		print self.obsList
	
class obsDict_online(object):
	"""
	Class to store observations of parsed data in online  mode. This class include 
	methods to add new partial observation to an absolute observation and a other 
	method for visual representation.
	"""
	def __init__(self):
		self.obsList = []

	def add(self,obs):
		if self.obsList:
			self.obsList = map(add, obs, self.obsList)
		else:
			self.obsList = obs

	def printt(self):
		print self.obsList

if __name__ == "__main__":
	
	main()
