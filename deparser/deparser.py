"""
parser -- This program take as input the features and the timestamps
obtaned fromdata analysis in order to extract the small amount of 
data related to anomalies in comparison to masive amounts of extracted data


Authors: Jose Manuel Garcia Gimenez (jgarciag@ugr.es)
		 
Last Modification: 04/Jul/2017

"""


import argparse
import time 
import os
import yaml
import glob
from datetime import datetime 
import re
from IPy import IP

# import flowparser


def main():


	startTime = time.time()

	# get config file from input arguments

	args = getArguments()


	# Check the config in yaml format

	try:
		deParserConfig = getConfiguration(args.config)
	except IOError:
		print "No such config file '%s'" %(args.config)
		exit(1)
	except yaml.scanner.ScannerError as e:
		print "Incorrect config file '%s'" %(args.config)
		print e.problem
		print e.problem_mark
		exit(1)
	try:
		dataSources = deParserConfig['DataSources']
		output = deParserConfig['Output']
	except KeyError as e:
		print "Missing config key: %s" %(e.message)
		exit(1)

	# Sources settings	

	sources = {}
	sources_config = {}
	tags = {}
	dateformats = {}
	dateregexp = {}
	SEPARATOR = {}
	
	for source in dataSources:
		sources[source] = {}

		try:
			sources_config[source] = getConfiguration(dataSources[source]['config'])
			sources[source]['files'] = glob.glob(dataSources[source]['data_raw'])	
			tags[source] = sources_config[source]['tag']
			dateformats[source] = sources_config[source]['timestamp_format']
			dateregexp[source] = sources_config[source]['timestamp_regexp']
			SEPARATOR[source] = sources_config[source]['separator']

		except:
			print "Configuration file error" 
			exit(1)


	# Dictionary of dictionaries with all the features from all the data sources.

	VARIABLES = {}
	FEATURES = {}
	structured = {}

	for source in sources_config:
		FEATURES[source] = {}
		VARIABLES[source] = {}
		structured[source] = sources_config[source]['structured']
 		for feature in sources_config[source]['FEATURES']:
 			
 			try:
				FEATURES[source][feature['name']] = feature
			except:
				print "Cofiguration file error: missing features"
				exit(1)

 		for variable in sources_config[source]['VARIABLES']:
 			
 			try:
				VARIABLES[source][variable['name']] = variable
			except:
				print "Cofiguration file error: missing vriables"
				exit(1)


	# Output settings

	try:
		OUTDIR = output['dir']
		if not OUTDIR.endswith('/'):
			OUTDIR = OUTDIR + '/'
	except (KeyError, TypeError):
		OUTDIR = 'OUTPUT/'
		print " ** Default output directory: '%s'" %(OUTDIR)
	try:
		OUTSTATS = output['stats']
	except (KeyError, TypeError):
		OUTSTATS = 'stats.log'
		print " ** Default log file: '%s'" %(OUTSTATS)

	# Create output directory and file

	if not os.path.exists(OUTDIR):
		os.mkdir(OUTDIR)
		print "** creating directory %s" %(OUTDIR)

	try:
		for source in dataSources:
			open(OUTDIR + "output_" + tags[source],'w') 
	except:
		print "error creating output file"
		exit(1)


	# Check input file, features and timestamp from the anomalies detected

	try:
		input_file = open(args.input, 'r')
	except IOError:
		print "No such input file '%s'" %(args.input)
		exit(1)


	# Check if the source files exist and are readable

	for source in sources:
		for source_file in sources[source]['files']:
			if source_file:
				try:
					stream = open(source_file,'r')
					stream.close()

				except IOError:
					print "No such config file '%s'" %(source_file)
					exit(1)
	

	#reverse tag dictionary to map tags into datasource files.

	inverse_tags = {v: k for k, v in tags.items()}
	

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



	# Print a summary of loaded parameters
	print "-------------------------------------------------------------------------------------------------"
	print "Data Sources:"
	for source in sources:
				print "	- " + str(tags[source]) + " --> Files: " + str(sources[source]['files'])

	print "FEATURES:"
	print " TOTAL " + (str(len(features))) + " features:  \n" + str(features) + "\n"
	print "-------------------------------------------------------------------------------------------------\n"

	print "TIMESTAMPS"
	print " TOTAL " + (str(len(timestamps))) + " timestamps:  \n" + str(timestamps) + "\n"
	print "-------------------------------------------------------------------------------------------------\n"
	
	print "Output:"
	print "  Directory: %s" %(OUTDIR)
	print "  Stats file: %s" %(OUTSTATS)
	print "\n-------------------------------------------------------------------------------------------------\n"
	print "Elapsed: %s" %(prettyTime(time.time() - startTime))
	print "\n-------------------------------------------------------------------------------------------------\n"



	if not features:

		sourcepath = sources[absouteSource]['files']
		tag = tags[absouteSource]
		dateFormat = dateformats[absouteSource]
		count_nf, count_cat, count_unstructured = logsByTimestamp(structured[absouteSource], timestamps, tag, sourcepath, dateFormat, OUTDIR, SEPARATOR[absouteSource], dateregexp[absouteSource])

		stats(count_nf,count_cat,count_unstructured, OUTDIR, OUTSTATS, startTime)
	
	# Generate outputs
	########################################################

	# NFDUMP QUERIES FOR NETFLOW SOURCES

	else:	
		count_nf = 0
		
		if 'netflow' in inverse_tags.keys():
			sFeatures = []	
			feat_delete = []  # list of already deparsed features 

			print "Generating and resolving nfdump queries...\n"

			for feature in features:

				if feature in FEATURES[inverse_tags['netflow']].keys():	
					sFields_nfdump(FEATURES[inverse_tags['netflow']],sFeatures,feature)
					feat_delete.append(feature)	


			# delete already deparsed features form features list.

			for f in feat_delete:
				features.remove(f)


			# append all the Variables with the conector and.

			Variables = ""
			for i in range(len(sFeatures) - 1):
				Variables +=  sFeatures[i] + " and " 

			if sFeatures:
				Variables += sFeatures[-1]



			# for each timestamp, generate the nfdump query with de filtering option extracted from the yaml file.

			for timestamp in timestamps:
				for file in  sources[inverse_tags['netflow']]['files']:
					if Variables:

						count_nf += 1
						date = parsedate(timestamp,dateformats[inverse_tags['netflow']])
						query = "nfdump -r " + file + ' -t ' + date + " '" + Variables +"' " + "' >> " + OUTDIR + "output_" + tags[inverse_tags['netflow']] 

						print query
						os.system(query)
		
			dataSources.pop(inverse_tags['netflow'],None)

		else:
			print "No nfdump queries..."

		print "\n-------------------------------------------------------------------------------------------------\n"
		print "Elapsed: %s" %(prettyTime(time.time() - startTime))
		print "\n-------------------------------------------------------------------------------------------------\n"

		


		##################################################################################################################################################################

		# NON NETFLOW SOURCES


		# iterate through features and timestams

		count_cat = 0
		count_unstructured = 0

		if features:
			for source in dataSources:
				print source

				tag = tags[source]
				sourcepath = sources[source]['files']
				formated_timestamps = format_timestamps(timestamps,dateformats[source])

				# If the source is structured, generate cat queries 
				if structured[source]:

					print "Generating and resolving Cat queries...\n"

					for feature in features:
						if feature in FEATURES[source].keys():
							
							patern = sFields_cat(feature, FEATURES[source], VARIABLES[source])

							# if the variable is regexp type, it is dealt with multiple grep pipe
							# and the function return both regexp paterns

							if len(patern) > 1:
								for timestamp in formated_timestamps:	
									for file in sourcepath:
										count_cat += 1

										query = "cat " + file + " | grep '" + timestamp + "' | grep -E '" + patern[1] + "' | grep -E '" + patern[0] + "' "  + " >> " + OUTDIR + "output_" + tag 	
										
										print query 
										os.system(query)

							else:
								for timestamp in formated_timestamps:	
									for file in sourcepath:
										count_cat += 1

										query = "cat " + file + " | grep '" + timestamp + "' | grep -E '" + patern[0] + "'" + " >> " + OUTDIR + "output_" + tag 	

										print query
										os.system(query)

					print "\n-------------------------------------------------------------------------------------------------\n"
					print "Elapsed: %s" %(prettyTime(time.time() - startTime))
					print "\n-------------------------------------------------------------------------------------------------\n"


				# Unstructured sources

				else:

					print "Dealing with unstructured sources...\n"

					output_file = open(OUTDIR + "output_" + tag,'w')

					for file in sourcepath:
						input_file = open(file,'r')
						line = input_file.readline()

						# Extract logs by separator defined in the given datasource
						if line:

							log = "" + line 	

							while line:

								log += line 
								
								if len(log.split(SEPARATOR[source])) > 1:
									logExtract = log.split(SEPARATOR[source])[0]

									# For each log, extract timestamp with regular expresions and check if it is in the 
									# input timestamps

									try:
										t = getUnstructuredTime(logExtract,dateregexp[source],dateformats[source])
										if str(t).strip() in formated_timestamps:
								
											# Check if features appear in the log to writhe in the file.
											count_unstructured = search_feature(FEATURES,VARIABLES,logExtract,features,output_file, source, count_unstructured)

									except:
										pass
													
									log = ""
									for n in logExtract.split(SEPARATOR[source])[1::]:
										log += n
				

								line = input_file.readline()

							# Deal with the last log, not processed during while loop.
							log += line

							try:								
								t = getUnstructuredTime(log,dateregexp[source],dateformats[source])
								if str(t) in timestamps:
									count_unstructured = search_feature(FEATURES,VARIABLES,log,features,output_file, source, count_unstructured)
						
							except:
								pass
			
						input_file.close()
						output_file.close()
 
 
		stats(count_nf, count_cat, count_unstructured, OUTDIR, OUTSTATS, startTime)

		# EXAMPLE QUERY CAT
		# query = cat home/administrador/CSV/ids | grep '4/5/2012 21:48' | grep -E 'misc'

		# EXAMPLE QUERY NFDUMP
		# query  = nfdump -r <nfcapd.file> -t <timestamp> 'flags A and packets < 4 and bytes < 151 and flags S and dst port = 25'

	

def stats(count_nf, count_cat, count_unstructured, OUTDIR, OUTSTATS, startTime):

	# Print stats
	print "\n--------------------------------------------------------------------------------------"	
	print "\nSearch finished:"
	print "Elapsed: %s" %(prettyTime(time.time() - startTime))
	print "\n nfdump queries: " + str(count_nf)
	print "    cat queries: " + str(count_cat)
	print "  total queries: " + str(count_nf + count_cat)
	print " unstructured logs found: " + str(count_unstructured)
	print "\n--------------------------------------------------------------------------------------\n"

	# Write stats in stats.log file.

	try:
		stats_file = open(OUTDIR + OUTSTATS,'w')
		stats_file.write("STATS:\n")
		stats_file.write("--------------------------------------------------------------------------------------\n")
		stats_file.write("nfdump queries: " + str(count_nf) + "\n")
		stats_file.write("   cat queries: " + str(count_cat) + "\n")
		stats_file.write(" total queries: " + str(count_nf + count_cat) + "\n")
		stats_file.write(" unstructured logs found: " + str(count_unstructured))

	except IOError as e:
		print "Stats file error: " + e.msg()


# Fuction to extract all logs from the datasource specified and timestamps.

def logsByTimestamp(structured, timestamps, tag, sourcepath, dateformat, OUTDIR, separator, dateregexp):

	print "\n#####################################################################################\n"
	print "No features especified, extracting all the logs of the timestamps and source especified "
	print "\n#####################################################################################\n\n\n"

	count_cat = 0
	count_nf = 0
	count_unstructured = 0

	if structured:

		for file in sourcepath:
			for timestamp in timestamps:

				if tag == 'netflow':
					query = "nfdump -r " + file + ' -t ' + parsedate(timestamp,dateformat) 
					count_cat += 1
					print query

				else:
					query = query = "cat " + file + " | grep '" + parsedate(timestamp,dateformat) 
					count_nf += 1
					print  query

	else:

		print "	Dealing with unstructured sources...\n"
		print "\n-------------------------------------------------------------------------------------------------\n"

		output_file = open(OUTDIR + "output_" + tag,'w')

		for file in sourcepath:
			input_file = open(file,'r')
			line = input_file.readline()

			# Extract logs by separator defined in the given datasource
			if line:
				log = "" + line 	

				while line:
					log += line 

					if len(log.split(separator)) > 1:
						logExtract = log.split(separator)[0]

						# For each log, extract timestamp with regular expresions and check if it is in the 
						# input timestamps
						t = getUnstructuredTime(logExtract,dateregexp,dateformat)
						
						if str(t) in timestamps:							
							output_file.write(logExtract)
							count_unstructured += 1
														
						log = ""
						for n in logExtract.split(separator)[1::]:
							log += n

					line = input_file.readline()

				# Deal with the last log, not processed during while loop.
				log += line
				t = getUnstructuredTime(log,dateregexp,dateformat)
				if str(t) in timestamps:
					output_file.write(logExtract)
					count_unstructured += 1


		input_file.close()
		output_file.close()

	return count_nf, count_cat, count_unstructured



def search_feature(FEATURES,VARIABLES,logExtract,features,output_file,source,count_unstructured):

	# Iterate through features, if all features of the given source appear in the log,
	# write the log in the output file.

	for feature in FEATURES[source].keys():	
		if feature in features:			

			fVariable = FEATURES[source][feature]['variable']
		
			varBol = False

			fValue = FEATURES[source][feature]['value']		
			fType = FEATURES[source][feature]['type']		


			match = re.search(VARIABLES[source][fVariable]['arg'],logExtract)

			if match:
				match = match.group(0)
				matchType = VARIABLES[source][fVariable]['matchtype']

				if fType == "regexp":
					if re.search(fValue, match):
						varBol = True

				elif fType == "single":	
						if str(fValue) == match:
							varBol = True

				elif fType == "multiple":
					if int(match) in fValue:
						varBol = True

				elif fType == "range":
					if int(match) >= fValue[0] and int(match) <= fValue[1]:
						varBol = True

			if varBol:
					output_file.write(logExtract + "\n\n")						
					count_unstructured += 1
					return count_unstructured

	return count_unstructured


# Fuction to parse date into YYYY-MM-DD hh:mm:ss 

def parsedate(timestamp, dateformat):

	# Method to change date format depending on the datasource
	# The format of each datasource is defined in the configuration file

	# output format. 
	# YYYY-MM-DD hh:mm:ss 		Example: 2012-04-05 23:31:00
	

	inDateformat = "%Y-%m-%d %H:%M:%S"
	return datetime.strptime(timestamp.strip(), inDateformat).strftime(dateformat)


def format_timestamps(timestamps, format2):

	timestamps_formated= []
	format1 = "%Y-%m-%d %H:%M:%S"

	for t in timestamps:
		timestamps_formated.append(str(datetime.strptime(t, format1).strftime(format2)))

	return timestamps_formated

def getArguments():

# Function to get input arguments using argparse.
# For more infor about the arguments, run deparser.py -h

	parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
	description='''Multivariate Analysis Deparsing Tool.''')
	parser.add_argument('config', metavar = 'CONFIG', help = 'Deparser Configuration File.')
	parser.add_argument('input', metavar = 'INPUT', help = 'Input file (vars and timestamps from multivariate analysis)')
	args = parser.parse_args()
	return args


def getConfiguration(config_file):

# Function to extract configurations from yaml files. 
# This info is stored into a dictionary.

	stream = file(config_file, 'r')
	conf = yaml.load(stream)
	stream.close()
	return conf



def prettyTime(elapsed):

# Function to change format of the time.

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

# Fuction to extrat timestamp from an unstructured source

	p = re.search(patern,log)
	try:
		date_string = p.group(0)
		d = datetime.strptime(date_string,dateFormat)
		d = d.replace(second = 00)
		
		return d.strftime(dateFormat)
	except:
		return None



def sFields_cat(feature, FEATURES, VARIABLES):

# Function to extract patern to search with grep in cat queries 
	
	fName = FEATURES[feature]['name']
	fVariable = FEATURES[feature]['variable']
	fType = FEATURES[feature]['type']
	fValue = FEATURES[feature]['value']

	variable = VARIABLES[fVariable]
	pos = variable['arg']

	if fType == 'regexp':
		return fValue, variable['arg'] 

	elif fType == 'single':		
		patern = "^(([^,]+)\,){" + str(pos) + "}" + str(fValue) 
		return [patern]

	elif fType == 'range':		
		start = fValue[0]
		end   = fValue[1]
		patern = "^(([^,]+)\,){" + str(pos) + "}[" + str(start) + '-' + str(end) + ']' 
		return [patern]


	elif fType == 'multiple':

		values = ""
		for f in range(len(fValue)):
			values += str(fValue[f]) + "|" 

		patern = "^(([^,]+)\,){" + str(pos) + "}" + values[:-1]
		return [patern]

	


def sFields_nfdump(nf_feat,sFeatures,feature):

# Function to exrtact nfdump filters from features

	fName = nf_feat[feature]['name']
	fVariable = nf_feat[feature]['variable']
	fType = nf_feat[feature]['type']
	fValue = nf_feat[feature]['value']


	# IP related features

	if fName.startswith('src_ip'):

		if fValue == "private":
			return "(src net 10.0.0.0/8 or src net 172.16.0.0/12 or src net 192.168.0.0/16)"

		if fValue == "public":
			return "not (src net 10.0.0.0/8 or src net 172.16.0.0/12 or src net 192.168.0.0/16)"

	elif fName.startswith('dst_ip'):

		if fValue == "public":
			return "not (dst net 10.0.0.0/8 or dst net 172.16.0.0/12 or dst net 192.168.0.0/16)"

		if fValue == "private":
			return "(dst net 10.0.0.0/8 or dst net 172.16.0.0/12 or dst net 192.168.0.0/16)"


	# Source port related features 

	if fName.startswith('sport'):

		if fType == 'single':
			sFeatures.append('src port '+ str(fValue))

		elif fType == 'multiple':
			for f in fValue:
				sFeatures.append('src port ' + str(f))

		elif fType == 'range':
			if isinstance(fValue, list) and len(fValue) == 2:
				start = fValue[0]
				end   = fValue[1]
				for f in range(start,end + 1):
					sFeatures.append('src port ' + str(f))


	# Destination port related features 

	elif fName.startswith('dport'):

		if fType == 'single':
			sFeatures.append('dst port '+ str(fValue))

		elif fType == 'multiple':
			for f in fValue:
				sFeatures.append('dst port ' + str(f))

		elif fType == 'range':
			if isinstance(fValue, list) and len(fValue) == 2:
				start = fValue[0]
				end   = fValue[1]
				for f in range(start,end + 1):
					sFeatures.append('dst port ' + str(f))


	# Protocol related features 

	elif fName.startswith('protocol'):
		
		if fType == 'single':
			sFeatures.append('proto '+ str(fValue).lower())


	# tcpflags  related features 

	elif fName.startswith('tcpflags'):
		
		if fType == 'regexp': 
			sFeatures.append('flags ' + fValue)


	# Type of service  related features 

	elif fName.startswith('srctos'):
		
		if fType == 'single':
			sFeatures.append('tos ' + str(fValue))


	# number of input and output packets related features 

	elif fName.startswith('in_npackets') or fName.startswith('out_npackets'):
		
		if fType == 'range':

			if isinstance(fValue, list) and len(fValue) == 2:
				start = fValue[0]
				end   = fValue[1]
				
				if start != 0 :
					start -1

				if end == 'Inf':
					sFeatures.append('packets > ' + str(start))

				else:
					sFeatures.append('(packets > ' + str(start) + ' and packets < ' + str(end+1) + ')')


	# number of input and output bytes related features 

	elif fName.startswith('in_nbytes') or fName.startswith('out_nbytes'):


		if fType == 'range':

			if isinstance(fValue, list) and len(fValue) == 2:
				start = fValue[0]
				end   = fValue[1]

				if start != 0 :
					start -1
				
				if end == 'Inf':
					sFeatures.append('bytes > ' + str(start))

				else:
					sFeatures.append('(bytes > ' + str(start) + ' and bytes < ' + str(end+1) + ')')


	# input interface  related features 

	elif fName.startswith('in_interface'):
		
		if fType == 'single':
			sFeatures.append('in if ' + str(fValue))


	# output interface  related features 

	elif fName.startswith('out_interface'):

		if fType == 'single':
			sFeatures.append('out if ' + str(fValue))


if __name__ == "__main__":
	main()