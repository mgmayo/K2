# Copyright 2018 The TensorFlow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A model for classifying light curves using a recurrent neural network.

See the base class (in astro_model.py) for a description of the general
framework of AstroModel and its subclasses.

The architecture of this model is:


                                     predictions
                                          ^
                                          |
                                       logits
                                          ^
                                          |
                                (fully connected layers)
                                          ^
                                          |
                                   pre_logits_concat
                                          ^
                                          |
                                    (concatenate)

              ^                           ^                          ^
              |                           |                          |
   (convolutional blocks 1)  (convolutional blocks 2)   ...          |
              ^                           ^                          |
              |                           |                          |
     time_series_feature_1     time_series_feature_2    ...     aux_features
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

# from astronet.astro_model import astro_model
from astronet.astro_model_mario import astro_model_mario


class AstroLSTMModelMario(astro_model_mario.AstroModelMario):
    """A model for classifying light curves using a bidirectional lstm recurrent neural net."""

    def __init__(self, features, labels, hparams, mode):
        """Basic setup. The actual TensorFlow graph is constructed in build().

    Args:
      features: A dictionary containing "time_series_features" and
          "aux_features", each of which is a dictionary of named input Tensors.
          All features have dtype float32 and shape [batch_size, length].
      labels: An int64 Tensor with shape [batch_size]. May be None if mode is
          tf.estimator.ModeKeys.PREDICT.
      hparams: A ConfigDict of hyperparameters for building the model.
      mode: A tf.estimator.ModeKeys to specify whether the graph should be built
          for training, evaluation or prediction.

    Raises:
      ValueError: If mode is invalid.
    """
        super(AstroLSTMModelMario, self).__init__(features, labels, hparams, mode)

    def _build_bi_lstm_layers(self, inputs, hparams, scope="bi-lstm"):
        """Builds convolutional layers.

    The layers are defined by convolutional blocks with pooling between blocks
    (but not within blocks). Within a block, all layers have the same number of
    filters, which is a constant multiple of the number of filters in the
    previous block. The kernel size is fixed throughout.

    Args:
      inputs: A Tensor of shape [batch_size, length].
      hparams: Object containing CNN hyperparameters.
      scope: Name of the variable scope.

    Returns:
      A Tensor of shape [batch_size, output_size], where the output size depends
      on the input size, kernel size, number of filters, number of layers,
      convolution padding type and pooling.
    """
        with tf.variable_scope(scope):
            net = tf.expand_dims(inputs, -1)  # [batch, length, channels]

            for i in range(1):
                num_hidden = 128
                timesteps = 701  # la dimension de la vista 701
                # Define weights
                weights = {
                    # Hidden layer weights => 2*n_hidden because of forward + backward cells
                    'out': tf.Variable(tf.random_normal([2 * num_hidden, 2]))
                }
                biases = {
                    'out': tf.Variable(tf.random_normal([2]))
                }
                with tf.variable_scope("block_%d" % (i + 1)):
                    for j in range(1):
                        """global_view = True
                        try:
                            net = tf.unstack(net, timesteps, 1) # vista global 701
                        except:
                            net = tf.unstack(net, 51, 1) # vista local 51
                            global_view=False
                        lstm_fw_cell = tf.contrib.rnn.BasicLSTMCell(num_hidden, forget_bias=1.0)
                        lstm_bw_cell = tf.contrib.rnn.BasicLSTMCell(num_hidden, forget_bias=1.0)
                        try:
                            outputs, _, _ = tf.contrib.rnn.static_bidirectional_rnn(lstm_fw_cell, lstm_bw_cell, net,
                                                                                    dtype=tf.float32)
                        except Exception:  # Old TensorFlow version only returns outputs not states
                            outputs = tf.contrib.rnn.static_bidirectional_rnn(lstm_fw_cell, lstm_bw_cell, net,
                                                                              dtype=tf.float32)
                        # print("**get shape111111***", net.get_shape())
                        #net = tf.matmul(outputs[-1], weights['out']) + biases['out']
                        #net = tf.reshape(net, [-1, None, 1])
                        if global_view:
                            net = tf.reshape(net, [-1, 701, 1])
                        else:
                            net = tf.reshape(net, [-1, 51, 1])# duda esta linea"""
                        lstm_fw_cell = tf.contrib.rnn.BasicLSTMCell(num_hidden, forget_bias=1.0)
                        lstm_bw_cell = tf.contrib.rnn.BasicLSTMCell(num_hidden*2, forget_bias=1.0)
                        multi_rnn_cell = tf.compat.v1.nn.rnn_cell.MultiRNNCell([lstm_fw_cell, lstm_bw_cell])
                        rnn_output, states = tf.nn.dynamic_rnn(multi_rnn_cell, net, dtype=tf.float32)

                        stacked_rnn_output = tf.reshape(rnn_output, [-1, 120])
                        stacked_outputs = tf.layers.dense(stacked_rnn_output, 1)
                        outputs = tf.reshape(stacked_outputs, [-1, 20, 1])

            print("*******NET****", net)
            print("**type*", type(net))
            print("**get shape***", net.get_shape())
            # Flatten.
            net.get_shape().assert_has_rank(3)
            net_shape = net.get_shape().as_list()
            output_dim = net_shape[1] * net_shape[2]
            net = tf.reshape(net, [-1, output_dim], name="flatten")

        return net

    def build_time_series_hidden_layers(self):
        """Builds hidden layers for the time series features.

    Inputs:
      self.time_series_features

    Outputs:
      self.time_series_hidden_layers
    """
        time_series_hidden_layers = {}
        for name, time_series in self.time_series_features.items():
            time_series_hidden_layers[name] = self._build_bi_lstm_layers(
                inputs=time_series,
                hparams=self.hparams.time_series_hidden[name],
                scope=name + "_hidden")

        self.time_series_hidden_layers = time_series_hidden_layers
