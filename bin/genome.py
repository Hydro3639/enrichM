#!/usr/bin/env python
###############################################################################
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    (at your option) any later version.                                      #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program. If not, see <http://www.gnu.org/licenses/>.     #
#                                                                             #
###############################################################################

__author__ = "Joel Boyd"
__copyright__ = "Copyright 2017"
__credits__ = ["Joel Boyd"]
__license__ = "GPL3"
__maintainer__ = "Joel Boyd"
__email__ = "joel.boyd near uq.net.au"
__status__ = "Development"
__version__ = "0.0.1"

###############################################################################
# imports
import os
import logging
from Bio import SeqIO

###############################################################################

class Genome:
	'''
	A genome object which collects all the attirbutes of an imput genome,
	including protein sequences and their annotations
	'''
	def __init__(self, path):

		self.protein_ordered_dict = {}
		self.path = path
		self.name = os.path.split(os.path.splitext(path)[0])[1]
		self.sequences = {}
		
		for protein_count, protein in enumerate(SeqIO.parse(path, 'fasta')):
			sequence = Sequence(protein.description, len(protein.seq))
		 	self.sequences[protein.name] = sequence
			self.protein_ordered_dict[protein_count] = protein.name
			
	def add(self, annotations, evalue_cutoff, bitscore_cutoff, 
		percent_aln_query_cutoff, percent_aln_reference_cutoff, annotation_type):
		'''
		Adds a series of annotations to the proteins within a genome.

		Parameters
		----------
		annotations						- String. Path to file containing either blast or
										  domtblout hmmsearch results. 
		evalue_cutoff					- Float. E-value threshold for annotations.
		bitscore_cutoff					- Float. Bit score threshold for annotations.
		percent_aln_query_cutoff		- Float. Threshold for the percent of the query 
										  that must be aligned to consider the annotation.
		percent_aln_reference_cutoff	- Float. Threshold for the percent of the reference
										  that must be aligned to consider the annotation.
		annotation_type					- String. Either 'KO', 'TIGRFAM', 'PFAM' or 'COG'

		'''
			
		# Load up annotation parser, and tell it what annotation type to expect
		ap = AnnotationParser(annotation_type)

		# If annotation type is a hmmsearch result
		if(annotation_type == AnnotationParser.PFAM or
		   annotation_type == AnnotationParser.TIGRFAM):
			# Set up an iterator to produce the results
			iterator = ap.from_hmmsearch_results(annotations, evalue_cutoff,
												 bitscore_cutoff, percent_aln_query_cutoff, 
												 percent_aln_reference_cutoff)

		# If annotation type is a blast result
		elif(annotation_type == AnnotationParser.KO or
			 annotation_type == AnnotationParser.COG):
			# Set up an iterator to produce the results
			iterator = ap.from_blast_results(annotations, evalue_cutoff, 
											 bitscore_cutoff, percent_aln_query_cutoff)


		for seqname, annotation, evalue, annotation_range in iterator:
			self.sequences[seqname].add(annotation, evalue, annotation_range, annotation_type)		

	def count(self, annotation):
		'''
		
		Parameters
		----------
		annotation - String. An annotation ID to return a frequency for
		
		Output
		------
		The number of times this annotation was encountered in the genome
		'''
		count = 0
		for sequence in self.sequences.values():
			if annotation in sequence.all_annotations():
				count+=1
		return count 
	
	def ordered_sequences(self):
		'''
		Iterator that yields that all protein coding Sequence objects in a genome in order.
		'''
		for sequence_id in sorted(self.protein_ordered_dict.keys()):
			yield self.sequences[self.protein_ordered_dict[sequence_id]]

class Sequence(Genome):
	'''
	Sequence object which collects all attributes of a sequence including its length,
	and annotations. Can compare current annotation with new annotaitons.
	'''
	def __init__(self, description, length):
		self.annotations = []	
		self.length = int(length)
		try:
			self.seqname, self.startpos, self.finishpos, self.direction, stats \
								= description.split(' # ')
			self.prod_id, self.partial, self.starttype, self.rbs_motif, self.rbs_spacer,  self.gc \
								= [x.split('=')[1] for x in stats.split(';')]
		except:
			raise Exception("Error parsing genome proteins. Was the output from prodigal?")

	def all_annotations(self):
		'''
		Returns a list of all annotations assigned to this sequence
		'''
		result = []
		for annotation in self.annotations:
			result.append(annotation.annotation)
		return result

	def seqdict(self):
		'''
		Output
		------
		A dictionary where each entry is a position in the sequence,
		and values are the annotation at that position. This is important
		in particular for pfam annotations as a protein can have >1 
		domains.
		'''
		seq_dict = {x:None for x in range(self.length)}
		for annotation in self.annotations:
			for position in annotation.region:
				seq_dict[position] = annotation.annotation
		return seq_dict


	def what(self, query_region):
		'''
		Return annotations assigned to a list of positions within a sequence.

		Parameters
		----------
		region 		- list. List of integers specifying the positions in the 
					  sequence to return annotations for
		Outputs
		-------
		Returns a list of equal length to region, containing the annotation of
		each position.
		'''
		result = []

		# Build reference dictionary for sequence
		seq_dict = self.seqdict()

		# Find annotation for each position in the sequence
		for position in query_region:
			result.append(seq_dict[position])
		return result

	def add(self, annotation, evalue, region, annotation_type):
		'''
		Return annotations assigned to a list of positions within a sequence.

		Parameters
		----------
		annotation 	- string. Annotation to assign to the sequence region
		evalue 		- float. Evalue awarded for the given annotation
		region		- list. List of integers specifying the positions in the 
					  sequence to annotate
		'''
		new_annotation = Annotation(annotation, evalue, region, annotation_type)
		if len([x for x in self.annotations if x.type == new_annotation.type]) > 0:
			for idx, previous_annotation in enumerate(self.annotations):
				if previous_annotation.type == new_annotation.type:
					if len(previous_annotation.region.intersection(new_annotation.region)) > 0:
						is_better = new_annotation.compare(previous_annotation)
						if is_better:
							self.annotations[idx] = new_annotation
		else:
			self.annotations.append(new_annotation)

	
class Annotation(Sequence):
	'''
	Annotation object that collects all attributes assocaited with a given
	annotation, like where it is in the sequence, its e-value and bit score,
	and what type of annotation it is.
	'''
	def __init__(self, annotation, evalue, region, annotation_type):

		self.annotation = annotation
		self.evalue 	= float(evalue)
		self.region		= set(region)
		self.type   	= annotation_type

	def compare(self, other_annotation):
		'''
		Compares evalue of current annotation with the evaulue of another annotation object. 			

		Parameters
		----------
		other_annotation: Annotation object.
		
		Output
		------
		Returns True if self is the better annotation or False if it isn't
		'''
		
		if self.evalue < other_annotation.evalue:
			return True
		else:
			return False

class AnnotationParser:
	'''
	Annotation parser class contains fucntions to parse hmmsearch domtblouts and blast results 
	currently for: KO, PFAM and TIGRFAM. COG to come	
	'''
	KO      	= 'KO_IDS.txt'
	PFAM    	= 'PFAM_IDS.txt'
	TIGRFAM 	= 'TIGRFAM_IDS.txt'
	COG 		= None ### ~ TODO: Not currently implemented

	def __init__(self, annotation_type):        
		

		data_directory = os.path.join(os.path.split(os.path.realpath(__file__))[0], '../data/ids/')
		if annotation_type == self.KO:
			ids = [x.strip() for x in open(os.path.join(data_directory,self.KO))]
		elif annotation_type == self.PFAM:
			ids = [x.strip() for x in open(os.path.join(data_directory,self.PFAM))]
		elif annotation_type == self.TIGRFAM:
			ids = [x.strip() for x in open(os.path.join(data_directory,self.TIGRFAM))]

	def from_blast_results(self,
						   blast_output_path,
						   evalue_cutoff,
						   bitscore_cutoff, 
						   percent_id_cutoff):
		'''
		Parse blast output in tab format.

		Parameters
		----------
		blast_output_path 	- String. Path to blast output file containing results.
							  Must be in blast output format 6
		evalue_cutoff		- Float. E-value threshold for annotations.
		bitscore_cutoff		- Float. Bit score threshold for annotations.
		percent_id_cutoff 	- Float. Percent identity threshold for annotations.
		
		Yields
		------
		A sequence name, annotation, E-value and region hit for every annottation result in 
		blast_output_path that pass a series of specified cutoffs
		'''

		logging.info("Parsing blast output file: %s" % blast_output_path)

		for line in open(blast_output_path):
			# Parse out important information from each line in blast output
			sline    = line.strip().split()
			evalue   = sline[10]
			bit      = sline[11]
			perc_id  = sline[2]
			seq_list = [int(x) for x in sline[6:8]]

			# If the annotation passes the specified cutoffs
			if(float(evalue) <= evalue_cutoff and
				float(bit) >= bitscore_cutoff and
				float(perc_id)  >= percent_id_cutoff):
					seqname = sline[0]
					annotation = sline[1].split('~')[1]
					yield seqname, annotation, evalue, range(min(seq_list), max(seq_list))

	def from_hmmsearch_results(self,
							   hmmsearch_output_path,
							   evalue_cutoff,
							   bitscore_cutoff, 
    						   percent_aln_query_cutoff,
    						   percent_aln_reference_cutoff):
		'''
		Parse input hmmsearch file

		Parameters 
		----------
		hmmsearch_output_path           - String. Path to domtblout file containing 
										  hmmsearch results.
		evalue_cutoff                   - Float. E-value threshold for annotations.
		bitscore_cutoff                 - Float. Bit score threshold for annotations.
		percent_aln_query_cutoff        - Float. Threshold for the percent of the query 
										  that must be aligned to consider the annotation.
		percent_aln_reference_cutoff    - Float. Threshold for the percent of the reference 
										  that must be aligned to consider the annotation.
		Yields
		------
		A sequence name, accession, E-value and region hit for every annottation result in 
		blast_output_path that pass a set of cutoffs
		'''

		logging.debug("    - Parsing hmmsearch output file: %s" % hmmsearch_output_path)

		# Filling in column
		for line in open(hmmsearch_output_path):
			
			# Skip headers
			if line.startswith('#'): continue
				
			# Parse HMMsearch line. '_'s represent unimportant entries. Line
			# is trimmed using [:22] to remove sequence description
			seqname, _, tlen, annotation, accession, qlen, evalue, score, \
			bias, _, _, c_evalue, i_evalue, dom_score, dom_bias, hmm_from, \
			hmm_to, seq_from, seq_to, _, _, acc = line.strip().split()[:22]				

			# Determine sequence and HMM spans
			seq_list = [int(seq_from), int(seq_to)]
			hmm_list = [int(hmm_from), int(hmm_to)]

			# Calculate percent of the query and reference aligned to each-other. 
			perc_seq_aln = (max(seq_list)-min(seq_list))/float(tlen)
			perc_hmm_aln = (max(seq_list)-min(seq_list))/float(qlen)

			# If the annotation passes the specified cutoffs
			if(float(evalue)<=evalue_cutoff and
				float(score)>=bitscore_cutoff and
				perc_seq_aln>=percent_aln_query_cutoff and
				perc_hmm_aln>=percent_aln_reference_cutoff):
				
				yield seqname, accession, evalue, range(min(seq_list), max(seq_list))