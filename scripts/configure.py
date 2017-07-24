#!/usr/bin/env python

import argparse

def main():
	args = get_arguments()
	
	instream = open(args.infile, 'r')
	outstream = open(args.output, 'w')
	
	outstream.write("VARIABLES:\n")
	outstream.write("# %s\n" %(args.field))
	
	line = instream.readline()
	while line:
		value = line.strip()
		var = args.prefix + value
		outstream.write("- name: %s\n" %(var))
		outstream.write("  field: %s\n" %(args.field))
		outstream.write("  type: single\n")
		outstream.write("  value: %s\n" %(value))
		line = instream.readline()

	instream.close()
	outstream.close()
	print "Written >> %s" %(args.output)
	

def get_arguments():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
	description='''Create variables configuration from a list of values.''')
	parser.add_argument('-o','--output', metavar='OUTPUT', default='configure_result.yaml', help='Output file. Default: "conf_result.dat".')
	parser.add_argument('-p','--prefix', metavar='PREFIX', default='pr_pr_', help='Prefix of the variable name. Default: "pr_pr_"')
	parser.add_argument('-f','--field', metavar='FIELD_NAME', default='pr.protocol', help='Field name. Default: "pr.protocol"')
	parser.add_argument('infile', metavar='FILE', help='Input data file (list of values)')
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	main()
