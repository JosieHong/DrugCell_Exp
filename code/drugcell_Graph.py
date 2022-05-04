import sys
import math
import torch
from torch.nn import Parameter
import torch.nn as nn
import torch.nn.functional as F
from util import *


class drugcell_graph(nn.Module):

	def __init__(self, term_size_map, term_direct_gene_map, dG, ngene, ndrug, root, num_hiddens_genotype, num_hiddens_drug, num_hiddens_final):
	
		super(drugcell_graph, self).__init__()

		self.root = root
		self.num_hiddens_genotype = num_hiddens_genotype
		self.num_hiddens_drug = num_hiddens_drug
		
		# dictionary from terms to genes directly annotated with the term
		self.term_direct_gene_map = term_direct_gene_map   

		# calculate the number of values in a state (term): term_size_map is the number of all genes annotated with the term
		self.cal_term_dim(term_size_map)		   
		
		# ngenes, gene_dim are the number of all genes	
		self.gene_dim = ngene			   
		self.drug_dim = ndrug

		# add modules for neural networks to process genotypes
		self.contruct_direct_gene_layer()
		self.construct_NN_graph(dG)

		# add modules for neural networks to process drugs	
		# self.construct_NN_drug()
		# add graph modules to process drugs
		self.construct_GNN_drug()

		# add modules for final layer
		final_input_size = num_hiddens_genotype + num_hiddens_drug[-1]
		self.add_module('final_linear_layer', nn.Linear(final_input_size, num_hiddens_final))
		self.add_module('final_batchnorm_layer', nn.BatchNorm1d(num_hiddens_final))
		self.add_module('final_aux_linear_layer', nn.Linear(num_hiddens_final,1))
		self.add_module('final_linear_layer_output', nn.Linear(1, 1))

	# calculate the number of values in a state (term)
	def cal_term_dim(self, term_size_map):

		self.term_dim_map = {}

		for term, term_size in term_size_map.items():
			num_output = self.num_hiddens_genotype
				
			# log the number of hidden variables per each term
			num_output = int(num_output)
			print("term\t%s\tterm_size\t%d\tnum_hiddens\t%d" % (term, term_size, num_output))
			self.term_dim_map[term] = num_output


	# build a layer for forwarding gene that are directly annotated with the term
	def contruct_direct_gene_layer(self):
		
		for term, gene_set in self.term_direct_gene_map.items():
			if len(gene_set) == 0:
				print('There are no directed asscoiated genes for', term)
				sys.exit(1)
	
			# if there are some genes directly annotated with the term, add a layer taking in all genes and forwarding out only those genes 		
			self.add_module(term+'_direct_gene_layer', nn.Linear(self.gene_dim, len(gene_set)))


	# add modules for fully connected neural networks for drug processing
	def construct_NN_drug(self):
		input_size = self.drug_dim

		for i in range(len(self.num_hiddens_drug)):
			self.add_module('drug_linear_layer_' + str(i+1), nn.Linear(input_size, self.num_hiddens_drug[i]))
			self.add_module('drug_batchnorm_layer_' + str(i+1), nn.BatchNorm1d(self.num_hiddens_drug[i]))
			self.add_module('drug_aux_linear_layer1_' + str(i+1), nn.Linear(self.num_hiddens_drug[i],1))
			self.add_module('drug_aux_linear_layer2_' + str(i+1), nn.Linear(1,1))

			input_size = self.num_hiddens_drug[i]

	# add graph gcn to drugcell
	def construct_GNN_drug(self):
		input_size = self.drug_dim

		for i in range(len(self.num_hiddens_drug)): 
			self.add_module('drug_graph_layer_' + str(i+1), simple_gcn_layer(input_size, self.num_hiddens_drug[i]))
			input_size = self.num_hiddens_drug[i]

	# start from bottom (leaves), and start building a neural network using the given ontology
	# adding modules --- the modules are not connected yet
	def construct_NN_graph(self, dG):

		self.term_layer_list = []   # term_layer_list stores the built neural network 
		self.term_neighbor_map = {}

		# term_neighbor_map records all children of each term	
		for term in dG.nodes():
			self.term_neighbor_map[term] = []
			for child in dG.neighbors(term):
				self.term_neighbor_map[term].append(child)

		while True:
			leaves = [n for n in dG.nodes() if dG.out_degree(n) == 0]
			#leaves = [n for n,d in dG.out_degree().items() if d==0]
			#leaves = [n for n,d in dG.out_degree() if d==0]

			if len(leaves) == 0:
				break

			self.term_layer_list.append(leaves)

			for term in leaves:
			
				# input size will be #chilren + #genes directly annotated by the term
				input_size = 0

				for child in self.term_neighbor_map[term]:
					input_size += self.term_dim_map[child]
		
				if term in self.term_direct_gene_map:
					input_size += len(self.term_direct_gene_map[term])

				# term_hidden is the number of the hidden variables in each state
				term_hidden = self.term_dim_map[term]

				self.add_module(term+'_linear_layer', nn.Linear(input_size, term_hidden))
				self.add_module(term+'_batchnorm_layer', nn.BatchNorm1d(term_hidden))
				self.add_module(term+'_aux_linear_layer1', nn.Linear(term_hidden,1))
				self.add_module(term+'_aux_linear_layer2', nn.Linear(1,1))

			dG.remove_nodes_from(leaves)


	# definition of forward function
	def forward(self, gene_input, drug_input, drug_graph): 

		# define forward function for genotype dcell #############################################
		term_gene_out_map = {}

		for term, _ in self.term_direct_gene_map.items():
			term_gene_out_map[term] = self._modules[term + '_direct_gene_layer'](gene_input)	

		term_NN_out_map = {}
		aux_out_map = {}

		for i, layer in enumerate(self.term_layer_list):

			for term in layer:

				child_input_list = []

				for child in self.term_neighbor_map[term]:
					child_input_list.append(term_NN_out_map[child])

				if term in self.term_direct_gene_map:
					child_input_list.append(term_gene_out_map[term])

				child_input = torch.cat(child_input_list,1)

				term_NN_out = self._modules[term+'_linear_layer'](child_input)				

				Tanh_out = torch.tanh(term_NN_out)
				term_NN_out_map[term] = self._modules[term+'_batchnorm_layer'](Tanh_out)
				aux_layer1_out = torch.tanh(self._modules[term+'_aux_linear_layer1'](term_NN_out_map[term]))
				aux_out_map[term] = self._modules[term+'_aux_linear_layer2'](aux_layer1_out)		

		# define forward function for drug dcell #################################################
		drug_out = drug_input
		for i in range(1, len(self.num_hiddens_drug)+1, 1):
			drug_out = F.relu(self._modules['drug_graph_layer_' + str(i)](drug_out, drug_graph))
		# max pooling
		drug_out = torch.max(drug_out, dim=1)[0]

		# connect two neural networks at the top #################################################
		final_input = torch.cat((term_NN_out_map[self.root], drug_out), 1)

		out = self._modules['final_batchnorm_layer'](torch.tanh(self._modules['final_linear_layer'](final_input)))
		term_NN_out_map['final'] = out

		aux_layer_out = torch.tanh(self._modules['final_aux_linear_layer'](out))
		aux_out_map['final'] = self._modules['final_linear_layer_output'](aux_layer_out)

		return aux_out_map, term_NN_out_map


class simple_gcn_layer(nn.Module):
	"""
	Simple GCN layer, similar to https://arxiv.org/abs/1609.02907
	"""
	def __init__(self, in_features, out_features, bias=False):
		super(simple_gcn_layer, self).__init__()
		self.in_features = in_features
		self.out_features = out_features
		self.weight = Parameter(torch.Tensor(in_features, out_features))
		if bias:
			self.bias = Parameter(torch.Tensor(1, 1, out_features))
		else:
			self.register_parameter('bias', None)
		self.reset_parameters()

	def reset_parameters(self):
		stdv = 1. / math.sqrt(self.weight.size(1))
		self.weight.data.uniform_(-stdv, stdv)
		if self.bias is not None:
			self.bias.data.uniform_(-stdv, stdv)

	def forward(self, input, adj): 
		'''
		Inputs: input size: (batch size, atom num, feature num)
				adj size: 	(batch size, atom num, atom num)
		'''
		support = torch.matmul(input, self.weight)
		output = torch.matmul(adj, support)
		if self.bias is not None:
			return output + self.bias
		else:
			return output