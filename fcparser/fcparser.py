#!/usr/bin/env python

"""
parser -- Program for parsing and processing raw network
data and preparing it for further multivariate analysis using
FaaC parser library.


Authors:    Jose Manuel Garcia Gimenez (jgarciag@ugr.es) 
			Alejandro Perez Villegas (alextoni@gmail.com)
		 
		 
Last Modification: 21/Sep/2017

"""

import multiprocessing as mp
import argparse
import glob
import datetime
import os
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
	stats = check_unused_sources(config, stats)

	# processing files
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

	print fuseObs(final_res, config)
	print "Elapsed: %s \n" %(prettyTime(time.time() - startTime))	



def process_unstr(config, source):
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
		
			print input_path.split('.')[-1]

			for fragStart,fragSize in frag_unstr(input_path,config['SEPARATOR'][source], config['Csize']):
				jobs.append( pool.apply_async(process_wrapper_unstr,(input_path,fragStart,fragSize,config, source,config['SEPARATOR'][source])) )

			for job in jobs:
				results.append(job.get())

		pool.close()
	return results

def process_str(config, source):

	results = []
	count = 0
	
	jobs = []

	for i in range(len(config['SOURCES'][source]['FILES'])):
		pool = mp.Pool(config['Cores'])
		input_path = config['SOURCES'][source]['FILES'][i]
		if input_path:
			count += 1
			tag = getTag(input_path)

			#Print some progress stats
			print "%s  #%s / %s  %s" %(source, str(count), str(len(config['SOURCES'][source]['FILES'])), tag)	
			print input_path.split('.')[-1]

			for fragStart,fragSize in frag_str(input_path, config['Csize']):
				jobs.append( pool.apply_async(process_wrapper_str,(input_path,fragStart,fragSize,config, source)))

			for job in jobs:
				results.append(job.get())

		pool.close()
	return results
	
def fuseObs(resultado, config):

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

def frag_unstr(fname,separator, size):
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
	separator = "\n"
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

def process_wrapper_unstr(file, fragStart, fragSize,config, source,separator):

	obsDictp = obsDict()
	with open(file) as f:
		f.seek(fragStart)
		lines = f.read(fragSize)

		log = ''
		for line in lines:
			log += line 

			if separator in log:

				tag, obs = process_log(log,config, source)
				obsDictp.add(obs,tag)
				log = ''	

		tag, obs = process_log(log,config, source)
		obsDictp.add(obs,tag)
	return obsDictp

def process_wrapper_str(file, fragStart, fragSize,config, source):

	separator = "\n" 
	obsDictp = obsDict()
	with open(file) as f:
		f.seek(fragStart)
		lines = f.read(fragSize).splitlines()

		for line in lines:
			tag, obs = process_log(line,config, source)
			obsDictp.add(obs,tag)

	return obsDictp

def process_log(log,config, source):
	 
	record = faaclib.Record(log,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source])
	obs = faaclib.AggregatedObservation(record, config['FEATURES'][source], config['Keys'])
	return normalize_timestamps(record.variables['timestamp'],config, source), obs.data

def normalize_timestamps(timestamp, config, source):
	try:
		input_format = config['SOURCES'][source]['CONFIG']['timestamp_format']
		start = config['Time']['start']
		window = config['Time']['window']

		t = datetime.datetime.strptime(str(timestamp), input_format)

		new_minute = t.minute - t.minute % window  

		t = t.replace(minute = new_minute, second = 0)
		if t.year == 1900:
			t = t.replace(year = start.year)

		return t
	except:
		
		return 0

def combine_results(dict1, dict2):
	### Combine results of parsing from multiple process,
	### Results are dicts with observations. The combination consist on 
	### mergind dicts, if a key is in both dicts, observations are added.
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

def check_unused_sources(config, stats):

	# Get a dictionary with all de var names 
	# to check if sources are unused due to choosen key
	if config['Keys']:
		var_names = {}
		for source in config['SOURCES']:
			var_names[source] = []
			for variable in  range(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])):
				var_names[source].append(config['SOURCES'][source]['CONFIG']['VARIABLES'][variable]['name'])

	# Count in witch source the key does not appear
		unused_sources = []
		for source in var_names:
			if isinstance(Keys,list):
				if not all(x in var_names[source] for x in config['Keys']):
					config['SOURCES'].pop(source, None)
					unused_sources.append(source)
			else:
				if config['Keys'] not in var_names[source]:
					config['SOURCES'].pop(source, None)
					unused_sources.append(source)

	# Count unused lines from all unused sources
	# in order to calculate a percentage of used entries.
		unused_lines = 0 
		for source in unused_sources:
			if source in stats['lines'].keys():				
				unused_lines += ['lines'][source]



		if unused_sources:
			print "\n\n###################################################################################################"
			print "                                                                                                       "
			print "                   WARNING: DATASOURCES UNUSED DUE TO CHOOSEN KEY                                      "
			print "                   UNUSED DATASOURCES:     " +str(unused_sources) +"                                   "
			print "                   PERCENTAGE OF USED ENRIES: " +str(float(stats['total_lines'] - unused_lines)*100/stats['total_lines']) 
			print "                                                                                                       "
			print "###################################################################################################\n\n"
			

			statsStream = open(stats['statsPath'], 'w')
			statsLine = "#------------------------------------------------\n"
			statsStream.write(statsLine)
			statsLine = "WARNING: DATASOURCES UNUSED DUE TO CHOOSEN KEY\n"
			statsStream.write(statsLine)
			statsLine = "UNUSED DATASOURCES:     " +str(unused_sources) +"\n"
			statsStream.write(statsLine)
			statsLine = "PERCENTAGE USED ENRIES: " +str(float(stats['total_lines'] - unused_lines)*100/stats['total_lines']) +"\n"
			statsStream.write(statsLine)
			statsLine = "#------------------------------------------------\n\n"
			statsStream.write(statsLine)

	
	# Extracting stats info, used and unused lines:

	stats['unused_lines'] = {}

	for source in config['SOURCES']:
		stats['unused_lines'][source] = 0

	if config['Keys']:
		if unused_sources:
			for unused_source in unused_sources:
				stats['unused_lines'][unused_source] = lines[unused_source]

	return stats

def create_stats(config):
	stats = {}
	# Create log files
	statsPath = config['OUTDIR'] + config['OUTSTATS']
	statsStream = open(statsPath, 'w')
	statsStream.write("STATS\n")
	statsStream.write("=================================================\n\n")
	statsStream.close()
	stats['statsPath'] = statsPath

	return stats

def count_entries(config,stats):

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

	weightsPath = config['OUTDIR'] + config['OUTW']
	weightsStream = open(weightsPath, 'w')
	weightsStream.write(', '.join(config['features']) + '\n')
	weightsStream.write(', '.join(config['weigthts']) + '\n')
	weightsStream.close()

def configSummary(config):
	
	# Print a summary of loaded parameters
	print "-----------------------------------------------------------------------"
	print "Data Sources:"
	for source in config['SOURCES']:
		print " * %s %s variables   %s features" %((source).ljust(18), str(len(config['SOURCES'][source]['CONFIG']['VARIABLES'])).ljust(2), str(len(config['SOURCES'][source]['CONFIG']['FEATURES'])).ljust(3))
	print " TOTAL %s features" %(str(sum(len(l) for l in config['FEATURES'].itervalues())))
	print
	print "Key:" 	
	aggrStr = ', '.join(config['Keys']) if isinstance(config['Keys'],list) else config['Keys']
	print aggrStr
	print
	print "Output:"
	print "  Directory: %s" %(config['OUTDIR'])
	print "  Stats file: %s" %(config['OUTSTATS'])
	print "  Weights file: %s" %(config['OUTW'])
	print "-----------------------------------------------------------------------\n"
	
def loadConfig(output, dataSources, parserConfig):


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
		##
		## TO DO
		##
		pass

	try: 
		Configuration['Cores'] = int(parserConfig['Processes'])

	except:
		##
		## TO DO
		##
		pass

	try: 
		Configuration['Csize'] = 1024 * int(parserConfig['Chunk_size'])

	except:
		##
		##
		##
		pass


	# Sources settgins
	Configuration['SOURCES'] = {}
	for source in dataSources:
		Configuration['SOURCES'][source] = {}
		Configuration['SOURCES'][source]['CONFIG'] = getConfiguration(dataSources[source]['config'])
		Configuration['SOURCES'][source]['FILES'] = glob.glob(dataSources[source]['data'])

	try:
		Configuration['Keys'] = parserConfig['Keys']
	except KeyError as e:
		Configuration['Keys'] = None 


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

		else:
			for i in range(len(Configuration['SOURCES'][source]['CONFIG']['VARIABLES'])):
				Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['vType'] = Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['matchtype']
				Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['vName'] = Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['name']
				Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['vWhere']  = Configuration['SOURCES'][source]['CONFIG']['VARIABLES'][i]['where']


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
				print Configuration['FEATURES'][source][i]
				exit(1)				
			try:
				Configuration['weigthts'].append(str(feat['weight']))
			except:
				Configuration['weigthts'].append('1')

	return Configuration

def getTag(filename):
	tagSearch = re.search("(\w*)\.\w*$", filename)
	if tagSearch:
		return tagSearch.group(1)
	else:
		return None

def file_uns_len(fname, separator):

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
	stream = file(config_file, 'r')
	conf = yaml.load(stream)
	stream.close()
	return conf

def file_len(fname):
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1

def getArguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Multivariate Analysis Parsing Tool.''')
	parser.add_argument('config', metavar='CONFIG', help='Parser Configuration File.')
	args = parser.parse_args()
	return args

class obsDict(object):
	"""docstring for Observation"""
	def __init__(self):
		self.obsList = {}

	def add(self,obs,tag):
		if tag in self.obsList.keys():
			self.obsList[tag] = map(add, obs, self.obsList[tag])
		else:
			self.obsList[tag] = obs

	def printt(self):
		print self.obsList
	

if __name__ == "__main__":
	
	main()
