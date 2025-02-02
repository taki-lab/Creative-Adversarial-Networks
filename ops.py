import math
import numpy as np 
import tensorflow as tf
import tf_slim as slim

from tensorflow.python.framework import ops

from utils import *

try:
  image_summary = tf.image_summary
  scalar_summary = tf.scalar_summary
  histogram_summary = tf.histogram_summary
  merge_summary = tf.merge_summary
  SummaryWriter = tf.train.SummaryWriter
except:
  image_summary = tf.compat.v1.summary.image
  scalar_summary = tf.compat.v1.summary.scalar
  histogram_summary = tf.compat.v1.summary.histogram
  merge_summary = tf.compat.v1.summary.merge
  SummaryWriter = tf.compat.v1.summary.FileWriter

if "concat_v2" in dir(tf):
  def concat(tensors, axis, *args, **kwargs):
    return tf.concat_v2(tensors, axis, *args, **kwargs)
else:
  def concat(tensors, axis, *args, **kwargs):
    return tf.concat(tensors, axis, *args, **kwargs)

def conv_out_size_same(size, stride):
  return int(math.ceil(float(size) / float(stride)))

def sigmoid_cross_entropy_with_logits(x, y):
      try:
        return tf.nn.sigmoid_cross_entropy_with_logits(logits=x, labels=y)
      except:
        return tf.nn.sigmoid_cross_entropy_with_logits(logits=x, targets=y)

def layer_norm(inputs, name):
   return slim.layer_norm(inputs, scope=name)

class batch_norm(object):
  def __init__(self, epsilon=1e-5, momentum = 0.9, name="batch_norm"):
    with tf.compat.v1.variable_scope(name):
      self.epsilon  = epsilon
      self.momentum = momentum
      self.name = name

  def __call__(self, x, train=True):
    return slim.batch_norm(x,
                      decay=self.momentum, 
                      updates_collections=None,
                      epsilon=self.epsilon,
                      scale=True,
                      is_training=train,
                      scope=self.name)

def conv_cond_concat(x, y):
  """Concatenate conditioning vector on feature map axis."""
  x_shapes = tf.shape(input=x)
  y_shapes = tf.shape(input=y)
  return concat([
    x, y*tf.ones([x_shapes[0], x_shapes[1], x_shapes[2], y_shapes[3]])], 3)

def conv2d(input_, output_dim, 
       k_h=5, k_w=5, d_h=2, d_w=2, stddev=0.02,
       name="conv2d",padding='SAME'):
  with tf.compat.v1.variable_scope(name):
    if padding=='VALID':
      paddings = np.array([[0,0],[1,1],[1,1],[0,0]])
      input_ = tf.pad(tensor=input_, paddings=paddings)
    w = tf.compat.v1.get_variable('w', [k_h, k_w, input_.get_shape()[-1], output_dim],
              initializer=tf.compat.v1.truncated_normal_initializer(stddev=stddev))
    conv = tf.nn.conv2d(input=input_, filters=w, strides=[1, d_h, d_w, 1], padding=padding)

    biases = tf.compat.v1.get_variable('biases', [output_dim], initializer=tf.compat.v1.constant_initializer(0.0))
    out_shape = [-1] + conv.get_shape()[1:].as_list()
    conv = tf.reshape(tf.nn.bias_add(conv, biases), out_shape) 
    
    return conv

def resizeconv(input_, output_shape,
		k_h=5, k_w=5, d_h=2, d_w=2, stddev=0.02,
		name="resconv"):
  with tf.compat.v1.variable_scope(name):
    
    resized = tf.image.resize(input_,((output_shape[1]-1)*d_h + k_h-4, (output_shape[2]-1)*d_w + k_w-4), method=tf.image.ResizeMethod.NEAREST_NEIGHBOR)
    #The 4 is because of same padding in tf.nn.conv2d.
    w = tf.compat.v1.get_variable('w', [k_h, k_w, resized.get_shape()[-1], output_shape[-1]],
		initializer=tf.compat.v1.truncated_normal_initializer(stddev=stddev))
    resconv = tf.nn.conv2d(input=resized, filters=w, strides=[1, d_h, d_w, 1], padding='SAME')
    biases = tf.compat.v1.get_variable('biases', output_shape[-1], initializer=tf.compat.v1.constant_initializer(0.0))
    
    return tf.nn.bias_add(resconv, biases)

def deconv2d(input_, output_shape,
       k_h=5, k_w=5, d_h=2, d_w=2, stddev=0.02,
       name="deconv2d"):
  with tf.compat.v1.variable_scope(name):
    static_shape = input_.get_shape().as_list()
    dyn_input_shape = tf.shape(input=input_)
    batch_size = dyn_input_shape[0]
    out_h = output_shape[1]
    out_w = output_shape[2]
    out_shape = tf.stack([batch_size, out_h, out_w, output_shape[-1]])

    w = tf.compat.v1.get_variable('w', [k_h, k_w, output_shape[-1], input_.get_shape()[-1]],
              initializer=tf.compat.v1.random_normal_initializer(stddev=stddev))
     
    deconv = tf.nn.conv2d_transpose(input_, w, output_shape=out_shape,
                strides=[1, d_h, d_w, 1])
    biases = tf.compat.v1.get_variable('biases', [output_shape[-1]], initializer=tf.compat.v1.constant_initializer(0.0))
    deconv = tf.nn.bias_add(deconv, biases)
    #deconv = tf.reshape(tf.nn.bias_add(deconv, biases), tf.shape(deconv))
    deconv.set_shape([None] + output_shape[1:])
    return deconv

def lrelu(x, leak=0.2, name="lrelu"):
  return tf.maximum(x, leak*x)

def linear(input_, output_size, scope=None, stddev=0.02, bias_start=0.0):
  shape = input_.get_shape().as_list()
  with tf.compat.v1.variable_scope(scope or "Linear"):
    matrix = tf.compat.v1.get_variable("Matrix", [shape[1], output_size], tf.float32,
                 tf.compat.v1.random_normal_initializer(stddev=stddev))
    bias = tf.compat.v1.get_variable("bias", [output_size],
      initializer=tf.compat.v1.constant_initializer(bias_start))
    return tf.matmul(input_, matrix) + bias
