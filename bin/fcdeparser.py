"""
parser -- This program take as input the features and the timestamps
obtaned fromdata analysis in order to extract the small amount of 
data related to anomalies in comparison to masive amounts of extracted data


Authors: Jose Manuel Garcia Gimenez (jgarciag@ugr.es)
		 
Last Modification: 29/Sep/2017

"""


import argparse
import time 
import os
import gzip
import yaml
import glob
import faac
from datetime import datetime 
import re
from IPy import IP


def main():
	startTime = time.time()

	# Get configuration
	configfile = getArguments()
	parserConfig = faac.getConfiguration(configfile.config)
	output = parserConfig['Deparsing_output']
	threshold = parserConfig['Deparsing_output']['threshold']
	dataSources = parserConfig['DataSources']
	config = faac.loadConfig(output, dataSources, parserConfig)
	deparsInput = getDeparsInput(configfile,config)


	# Not Netflow datasources
	count_structured = 0
	count_unstructured = 0
	count_tots = 0
	count_totu = 0
	count_source = 0

	# iterate through features and timestams
	if deparsInput['features']:
		for source in dataSources:
			print source
			count_source = 0
			sourcepath = config['SOURCES'][source]['FILESDEP']
			formated_timestamps = format_timestamps(deparsInput['timestamps'],config['SOURCES'][source]['CONFIG']['timestamp_format'])
			# Structured sources
			if config['STRUCTURED'][source]:
				(cs, ct) = stru_deparsing(config,threshold, sourcepath, deparsInput, source, formated_timestamps)
				count_structured += cs
				count_tots += ct

			# Unstructured sources
			else:
				(cu, ct) = unstr_deparsing(config,threshold, sourcepath, deparsInput,source, formated_timestamps)
				count_unstructured += cu
				count_totu += ct

			print "\n---------------------------------------------------------------------------\n"
			print "Elapsed: %s" %(prettyTime(time.time() - startTime))
			print "\n---------------------------------------------------------------------------\n"

	stats(count_structured, count_tots, count_unstructured, count_totu, config['OUTDIR'], config['OUTSTATS'], startTime)

	

def print_loadSummary(config,deparsInput,startTime):
	'''
	Print a summary of loaded parameters
	'''
	print "------------------------------------------------------------------------"
	print "Data Sources:"
	for source in config['sources_files']:
				print "	- " + str(config['tags'][source]) + " --> Files: " + str(config['sources_files'][source]['files'])

	print "FEATURES:"
	print " TOTAL " + (str(len(deparsInput['features']))) + " features:  \n" + str(deparsInput['features']) + "\n"
	print "------------------------------------------------------------------------\n"

	print "TIMESTAMPS"
	print " TOTAL " + (str(len(deparsInput['timestamps']))) + " timestamps:  \n" + str(deparsInput['timestamps']) + "\n"
	print "------------------------------------------------------------------------\n"
	
	print "Output:"
	print "  Directory: %s" %(config['OUTDIR'])
	print "  Stats file: %s" %(config['OUTSTATS'])
	print "\n------------------------------------------------------------------------\n"
	print "Elapsed: %s" %(prettyTime(time.time() - startTime))
	print "\n------------------------------------------------------------------------\n"

def getDeparsInput(configfile,config):
	'''
	Extract the information from the detection step (timestamps and features) for the anomaly that 
	is desired to be deparsed
	'''
	deparsInput = {}

	try:
		input_file = open(configfile.input, 'r')
	except IOError:
		print "No such input file '%s'" %(configfile.input)
		exit(1)

	#Extract features and timestams from the input file.
	line = input_file.readline()

	features = []
	timestamps = []
	featuresBol = False
	timeBol = False

	while line:
		if "features:" in line :
			featuresBol = True

		if "timestamps:" in line :
			timeBol = True
			featuresBol = False

		if featuresBol:
			try: 
				features.append(line.split("=")[1].strip())
			except:
				pass

		if timeBol:
			try: 
				timestamps.append(line.split("=")[1].strip())
			except:
				pass
		
		line = input_file.readline()

	if not (config['Time']['window'] == 1  or config['Time']['window'] == None):
		temp = []
		for timestamp in timestamps:
			print timestamp
			for i in range(config['Time']['window'] ):
				t = datetime.strptime(timestamp,"%Y-%m-%d %H:%M:%S")
				new_minute = (t.minute + i) % 60
				new_hour = (t.hour + i/60) % 24
				new_day = (t.day + i/(24*60)) 
				t = t.replace(day = new_day, hour = new_hour, minute = new_minute, second = 0)	
				temp.append(str(t))


		timestamps = temp

	deparsInput['features'] = features
	deparsInput['timestamps'] = timestamps
	
	return deparsInput	

def stru_deparsing(config,threshold, sourcepath, deparsInput, source, formated_timestamps):
	'''
	Deparsing process for structured data sources like csv.
	'''
	sources_config = config['SOURCES']
	OUTDIR = config['OUTDIR']
	features = deparsInput['features']

	FEATURES = {}
	VARIABLES = {}

	for feature in config['SOURCES'][source]['CONFIG']['FEATURES']:
		try:
			FEATURES[feature['name']] = feature
		except:
			print "Cofiguration file error: missing features"
			exit(1)

	for variable in config['SOURCES'][source]['CONFIG']['VARIABLES']:
		try:
			VARIABLES[variable['name']] = variable
		except:
			print "Cofiguration file error: missing vriables"
			exit(1)




	count_structured = 0
	count_tot = 0
	output_file = open(OUTDIR + "output_" + source,'w')
	feat_appear = {}
	for file in sourcepath:
		feat_appear[file] = []
		if file.endswith('.gz'):
			input_file = gzip.open(file,'r')
		else:
			input_file = open(file,'r')

		line = input_file.readline()

		# First read to generate list of number of appearances
		while line:
			try:
				t = getStructuredTime(line,0,config['SOURCES'][source]['CONFIG']['timestamp_format'])		

				if str(t).strip() in formated_timestamps:
					# extract amount of features that appear in each line included in timestamps analyzed.
					feat_appear[file].append(search_features_str(line,features, FEATURES, VARIABLES))
			except:
			  	print "error deparsing source:" + source
					
			line = input_file.readline()
		input_file.close()

	# Obtain number of features needed to extract the log with the threshold given
	features_needed = len(features)
	count = 0
	while count < int(threshold) and (not features_needed <= 1):
		for file in feat_appear:
			count += feat_appear[file].count(int(features_needed))
		features_needed -= 1

	# Re-read the file extracting the raw data
	for file in sourcepath:
		index = 0
		if file.endswith('.gz'):
			input_file = gzip.open(file,'r')
		else:
			input_file = open(file,'r')

		input_file.seek(0)
		line = input_file.readline()
			
		while line:
			count_tot += 1	
			try:
				t = getStructuredTime(line,0,config['SOURCES'][source]['CONFIG']['timestamp_format'])		
				if str(t).strip() in formated_timestamps:
					if feat_appear[file][index] >= features_needed:
						output_file.write(line + "\n")
						count_structured += 1	
					index += 1
			except:
				pass
			
			line = input_file.readline()
		input_file.close()
	output_file.close()

	return (count_structured, count_tot)

def unstr_deparsing(config, threshold, sourcepath, deparsInput, source, formated_timestamps):
	'''
	Deparsing process for unstructured text based data sources like a log file.
	'''
	OUTDIR = config['OUTDIR']
	features = deparsInput['features']

	selection = []
	for i in range(len(config['FEATURES'][source])):
		if config['FEATURES'][source][i]['name'] in features:
			selection.append(i)

	FEATURES_sel = []
	for i in selection:
		FEATURES_sel.append(config['FEATURES'][source][i])

	VARIABLES = {}

	for variable in config['SOURCES'][source]['CONFIG']['VARIABLES']:
		try:
			VARIABLES[variable['name']] = variable
		except:
			print "Cofiguration file error: missing vriables"
			exit(1)
	
	count_unstructured = 0
	count_tot = 0
	print OUTDIR + "output_" + source
	output_file = open(OUTDIR + "output_" + source,'w')

	# while count_source < lines[source]*0.01 and (not features_needed <= 0) : 
	feat_appear = {}
	for file in sourcepath:
		feat_appear[file] = []	

		if file.endswith('.gz'):
			input_file = gzip.open(file,'r')
		else:
			input_file = open(file,'r')

		line = input_file.readline()


		# First read to generate list of number of appearances
		if line:
			log = "" 	
			while line:
				log += line 
	
				if len(log.split(config['SEPARATOR'][source])) > 1:
					logExtract = log.split(config['SEPARATOR'][source])[0]
					
					# For each log, extract timestamp with regular expresions and check if it is in the 
					# input timestamps
					try:

						t = getUnstructuredTime(logExtract, VARIABLES['timestamp']['where'], config['SOURCES'][source]['CONFIG']['timestamp_format'])					
						if str(t).strip() in formated_timestamps:	
							# Check if features appear in the log to write in the file.
							record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['All'])
							obs = faac.Observation.fromRecord(record, FEATURES_sel)
							feat_appear[file].append(sum( [obs.data[i].value for i in range(len(obs.data))]))
					except:
						pass
						
					log = ""
					for n in logExtract.split(config['SEPARATOR'][source])[1::]:
						log += n
				line = input_file.readline()

			# Deal with the last log, not processed during while loop.
			log += line
			try:								
				t = getUnstructuredTime(log, VARIABLES['timestamp']['where'], config['SOURCES'][source]['CONFIG']['timestamp_format'])
				if str(t) in timestamps:
					record = faac.Record(logExtract,config['SOURCES'][source]['CONFIG']['VARIABLES'], config['STRUCTURED'][source], config['All'])
					obs = faac.Observation.fromRecord(record, FEATURES_sel)
					feat_appear[file].append(sum( [obs.data[i].value for i in range(len(obs.data))]))
			except:
				pass

		input_file.close()

	# Obtain number of features needed to extract the log
	features_needed = len(features)
	count = 0
	while count < int(threshold) and (not features_needed <= 1):
		for file in feat_appear:
			count += feat_appear[file].count(int(features_needed))

		print("There are " + str(count) + " unstructured logs with more than " + str(features_needed) + " matching features...")
		features_needed -= 1

	# Re-read the file
	for file in sourcepath:
		index = 0

		if file.endswith('.gz'):
			input_file = gzip.open(file,'r')
		else:
			input_file = open(file,'r')

		input_file.seek(0)
		line = input_file.readline()
			
		if line:
			log = "" + line 	
			while line:
				log += line 
				if len(log.split(config['SEPARATOR'][source])) > 1:
					count_tot += 1	
					logExtract = log.split(config['SEPARATOR'][source])[0]
					
					# For each log, extract timestamp with regular expresions and check if it is in the 
					# input timestamps
					try:
						t = getUnstructuredTime(logExtract, VARIABLES['timestamp']['where'], config['SOURCES'][source]['CONFIG']['timestamp_format'])												
						if str(t).strip() in formated_timestamps:	
							# Check if features appear in the log to write in the file.
							if feat_appear[file][index] > features_needed:
								output_file.write(logExtract + config['SEPARATOR'][source])
								count_unstructured += 1	
							index += 1
					except:
						pass

					log = ""
					for n in logExtract.split(config['SEPARATOR'][source])[1::]:
						log += n
				line = input_file.readline()

		input_file.close()
	output_file.close()
	return (count_unstructured, count_tot)

def stats( count_structured, count_tots, count_unstructured, count_totu, OUTDIR, OUTSTATS, startTime):
	'''
	Print and write stats from the deparsing process
	'''

	print "\n---------------------------------------------------------------------------"	
	print "\nSearch finished:"
	print "Elapsed: %s" %(prettyTime(time.time() - startTime))
	# print "\n Nfdump queries: " + str(count_nf)
	print " Structured logs found:  " + str(count_structured) + ' out of ' + str(count_tots) 
	print " Unstructured logs found: " + str(count_unstructured) + ' out of ' + str(count_totu)
	print "\n---------------------------------------------------------------------------\n"

	# Write stats in stats.log file.
	try:
		stats_file = open(OUTDIR + OUTSTATS,'w')
		stats_file.write("STATS:\n")
		stats_file.write("---------------------------------------------------------------------------\n")
		# stats_file.write("Nfdump queries: " + str(count_nf) + "\n")
		stats_file.write(" Structured logs found: " + str(count_structured) + ' out of ' + str(count_tots) + "\n")
		stats_file.write(" Unstructured logs found: " + str(count_unstructured) + ' out of ' + str(count_totu))

	except IOError as e:
		print "Stats file error: " + e.msg()


def search_features_str(line,features,FEATURES,VARIABLES):
	'''
	Function that take as an input one data record and obtain the number of features that appear in the log 
	from the input features for structured sources	
	'''

	feature_count = 0
	for feature in features:

		try:
			fName = FEATURES[feature]['name']
			fVariable = FEATURES[feature]['variable']
			fType = FEATURES[feature]['matchtype']
			fValue = FEATURES[feature]['value']
			variable = VARIABLES[fVariable]

			pos = variable['where']

			line_split = line.split(',')

			if fType == 'regexp':		
				try:
					re.search(fValue, line_split[pos])
					feature_count += 1
				except:
					pass

			elif fType == 'single':		
				if line_split[pos].strip() == str(fValue):
					feature_count += 1

			elif fType == 'range':		

				start = fValue[0]
				end   = fValue[1]
				
				if (int(line_split[pos]) < end) and (int(line_split[pos]) > start):
					feature_count += 1 

			elif fType == 'multiple':
				for value in fValue:
					if line_split[pos] == value:
						feature_count += 1
		except:
		 	pass

	return feature_count

def parsedate(timestamp, dateformat):
	'''
	Method to change date format depending on the datasource
	The format of each datasource is defined in the configuration file

	output format. 
	YYYY-MM-DD hh:mm:ss 		Example: 2012-04-05 23:31:00
	'''

	inDateformat = "%Y-%m-%d %H:%M:%S"
	return datetime.strptime(timestamp.strip(), inDateformat).strftime(dateformat)

def format_timestamps(timestamps, format2):
	'''
	Format a list of timestamps to an standar format.
	'''
	
	timestamps_formated= []
	format1 = "%Y-%m-%d %H:%M:%S"

	for t in timestamps:
		timestamps_formated.append(str(datetime.strptime(t, format1).strftime(format2)))

	return timestamps_formated

def getArguments():
	'''
	Function to get input arguments using argparse.
	For more infor about the arguments, run deparser.py -h
	'''

	parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
	description='''Multivariate Analysis Deparsing Tool.''')
	parser.add_argument('config', metavar = 'CONFIG', help = 'Deparser Configuration File.')
	parser.add_argument('input', metavar = 'INPUT', help = 'Input file (vars and timestamps from multivariate analysis)')
	args = parser.parse_args()
	return args

def getConfiguration(config_file):
	'''
	Function to extract configurations from yaml files. 
	This info is stored into a dictionary.
	'''

	stream = file(config_file, 'r')
	conf = yaml.load(stream)
	stream.close()
	return conf

def prettyTime(elapsed):
	'''
	Function to change format of the time, for a nice representation.
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

def getUnstructuredTime (log, patern, dateFormat):
	'''
	# Fuction to extrat timestamp from an unstructured source
	'''
	p = re.search(patern,log)
	try:
		date_string = p.group(0)
		d = datetime.strptime(date_string,dateFormat)
		d = d.replace(second = 00)
		
		return d.strftime(dateFormat)

	except:
		return None

def getStructuredTime(line, pos, dateFormat):
	'''
	# Fuction to extrat timestamp from an structured source
	'''

	valueList = line.split(',')
	rawTime = valueList[pos].split('.')[0]
	time = datetime.strptime(rawTime, dateFormat)
	time = time.replace(second = 00)
	return time

if __name__ == "__main__":
	main()
