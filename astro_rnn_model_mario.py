

"""A model for classifying light curves using a recurrent neural network.

See the base class (in astro_model.py) for a description of the general
framework of AstroModel and its subclasses.

The architecture of this model is:


                                     predictions
                                          ^
                                          |
                                       logits (map 0 to 1)
                                          ^
                                          |
                                (fully connected layers)
                                          ^
                                          |
                                   pre_logits_concat (raw predction data)
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


class AstroRNNModelMario(astro_model_mario.AstroModelMario):
    """A model for classifying light curves using a recurrent neural net."""

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
        super(AstroRNNModelMario, self).__init__(features, labels, hparams, mode)

    def _build_rnn_layers(self, inputs, hparams, scope="rnn"):
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

            for i in range(hparams.rnn_num_blocks): # bloques

                with tf.variable_scope("block_%d" % (i + 1)):
                    for j in range(hparams.rnn_block_size): # 1 capa por bloque
                        basic_cell = tf.contrib.rnn.BasicRNNCell(num_units=hparams.num_neurons, activation=tf.nn.relu)
                        rnn_output, states = tf.nn.dynamic_rnn(basic_cell, net, dtype=tf.float32)

                        stacked_rnn_output = tf.reshape(rnn_output, [-1, hparams.num_neurons])
                        stacked_outputs = tf.layers.dense(stacked_rnn_output, hparams.num_output)
                        outputs = tf.reshape(stacked_outputs, [-1, hparams.num_windows, hparams.num_output])

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
            time_series_hidden_layers[name] = self._build_rnn_layers(
                inputs=time_series,
                hparams=self.hparams.time_series_hidden[name],
                scope=name + "_hidden")

        self.time_series_hidden_layers = time_series_hidden_layers
