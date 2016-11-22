import numpy as np

import theano
import theano.tensor as T

import lasagne
from lasagne.layers import InputLayer, DenseLayer, DropoutLayer
from lasagne.nonlinearities import sigmoid
from lasagne.layers import get_all_params, get_output
from lasagne.objectives import binary_crossentropy
from lasagne.updates import adam
from lasagne.layers import helper

from layers import ARC

from data_workers import OmniglotVerif

from main import train, test, save

import argparse


parser = argparse.ArgumentParser(description="CLI for setting hyper-parameters")
parser.add_argument("-n", "--expt-name", type=str, default="a_o_test", help="experiment name(for logging purposes)")
parser.add_argument("-l", "--learning-rate", type=float, default=5e-5, help="learning rate")
parser.add_argument("-i", "--image-size", type=int, default=32, help="side length of the square input image")

parser.add_argument("-w", "--attn-win", type=int, default=4, help="side length of square attention window")
parser.add_argument("-s", "--lstm-states", type=int, default=512, help="number of LSTM controller states")
parser.add_argument("-g", "--glimpses", type=int, default=8, help="number of glimpses per image")
parser.add_argument("-f", "--fg-bias-init", type=float, default=0.2, help="initial bias for the forget gate of LSTM controller")

parser.add_argument("-a", "--within-alphabet", action="store_false", help="select only the character pairs that within the alphabet ")
parser.add_argument("-b", "--batch-size", type=int, default=128, help="batch size")
parser.add_argument("-t", "--testing", action="store_true", help="report test set results")
parser.add_argument("-u", "--n-iter", type=int, default=100000, help="number of iterations")

parser.add_argument("-p", "--dropout", type=float, default=0.2, help="dropout on the input")

meta_data = vars(parser.parse_args())

for md in meta_data.keys():
	print md, meta_data[md]
	
expt_name = meta_data["expt_name"]
learning_rate = meta_data["learning_rate"]
image_size = meta_data["image_size"]
attn_win = meta_data["attn_win"]
glimpses = meta_data["glimpses"]
lstm_states = meta_data["lstm_states"]
fg_bias_init = meta_data["fg_bias_init"]
batch_size = meta_data["batch_size"]
dropout = meta_data["dropout"]
n_iter = meta_data["n_iter"]
within_alphabet = meta_data["within_alphabet"]
data_split = [30, 10]
meta_data["num_output"] = 2

print "... setting up the network"
X = T.tensor3("input")
y = T.imatrix("target")

l_in = InputLayer(shape=(None, image_size, image_size), input_var=X)
l_noise = DropoutLayer(l_in, p=dropout)
l_arc = ARC(l_noise, lstm_states=lstm_states, image_size=image_size, attn_win=attn_win, 
					glimpses=glimpses, fg_bias_init=fg_bias_init)
l_y = DenseLayer(l_arc, 1, nonlinearity=sigmoid)

prediction = get_output(l_y)
prediction_clean = get_output(l_y, deterministic=True)

loss = T.mean(binary_crossentropy(prediction, y))
accuracy = T.mean(T.eq(prediction_clean > 0.5, y), dtype=theano.config.floatX)

params = get_all_params(l_y)
updates = adam(loss, params, learning_rate=learning_rate)

meta_data["num_param"] = lasagne.layers.count_params(l_y)
print "number of parameters: ", meta_data["num_param"]

print "... compiling"
train_fn = theano.function([X, y], outputs=loss, updates=updates)
val_fn = theano.function([X, y], outputs=[loss, accuracy])

print "... loading dataset"
# TODO: Add option here for LFW in the furture
worker = OmniglotVerif(image_size=image_size, batch_size=batch_size, \
	data_split=data_split, within_alphabet=within_alphabet)

meta_data, best_params = train(train_fn, val_fn, worker, meta_data, \
	get_params=lambda: helper.get_all_param_values(l_y))

if meta_data["testing"]:
	print "... testing"
	helper.set_all_param_values(l_y, best_params)
	test(val_fn, worker, meta_data)

save(meta_data, best_params)