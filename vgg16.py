import inspect
import os

import numpy as np
import tensorflow as tf
import time

# 这个有什么作用？
VGG_MEAN = [103.939, 116.779, 123.68]

# define a vgg16 class
class Vgg16:
    def __init__(self, vgg16_npy_path=None):
        if vgg16_npy_path is None:
            # inspect.getfile(object): 返回对象的文件名
            path = inspect.getfile(Vgg16)
            # 获取文件的绝对路径
            path = os.path.abspath(os.path.join(path, os.pardir))
            path = os.path.join(path, "vgg16.npy")
            vgg16_npy_path = path
            print(path)

        self.data_dict = np.load(vgg16_npy_path, encoding='latin1').item()
        print("npy file loaded")

    # rgb即为输入图像，即x
    def build(self, rgb):
        """
        load variable from npy to build the VGG

        :param rgb: rgb image [batch, height, width, 3] values scaled [0, 1]
        """

        start_time = time.time()
        print("build model started")
        rgb_scaled = rgb * 255.0

        # Convert RGB to BGR
        # 感觉调换一下顺序比较好
        # red, green, blue = tf.split(axis=3, num_or_size_splits=3, value=rgb_scaled)
        red, green, blue = tf.split(value=rgb_scaled, num_or_size_splits=3, axis=3)
        assert red.get_shape().as_list()[1:] == [224, 224, 1], "red shape is not compatible"
        assert green.get_shape().as_list()[1:] == [224, 224, 1], 'green shape is not compatible'
        assert blue.get_shape().as_list()[1:] == [224, 224, 1], 'blue shape is not compatible'
        # then concat r,b,r to b,g,r，
        bgr = tf.concat(axis=3, values=[
            blue - VGG_MEAN[0],
            green - VGG_MEAN[1],
            red - VGG_MEAN[2],
        ])
        assert bgr.get_shape().as_list()[1:] == [224, 224, 3]

        # self.conv1_1 = self.conv_layer(bgr, "conv1_1")
        # self.conv1_2 = self.conv_layer(self.conv1_1, "conv1_2")
        # self.pool1 = self.max_pool(self.conv1_2, 'pool1')
        # channel=64
        self.conv1_1 = self.conv_layer(bgr, "conv1_1")
        self.conv1_2 = self.conv_layer(self.conv1_1, "conv1_2")
        self.pool1 = self.max_pool(self.conv1_2, 'pool1')

        # channel = 128
        self.conv2_1 = self.conv_layer(self.pool1, "conv2_1")
        self.conv2_2 = self.conv_layer(self.conv2_1, "conv2_2")
        self.pool2 = self.max_pool(self.conv2_2, 'pool2')

        # channel = 256
        self.conv3_1 = self.conv_layer(self.pool2, "conv3_1")
        self.conv3_2 = self.conv_layer(self.conv3_1, "conv3_2")
        self.conv3_3 = self.conv_layer(self.conv3_2, "conv3_3")
        self.pool3 = self.max_pool(self.conv3_3, 'pool3')

        # channel = 512
        self.conv4_1 = self.conv_layer(self.pool3, "conv4_1")
        self.conv4_2 = self.conv_layer(self.conv4_1, "conv4_2")
        self.conv4_3 = self.conv_layer(self.conv4_2, "conv4_3")
        self.pool4 = self.max_pool(self.conv4_3, 'pool4')

        # channle = 512
        self.conv5_1 = self.conv_layer(self.pool4, "conv5_1")
        self.conv5_2 = self.conv_layer(self.conv5_1, "conv5_2")
        self.conv5_3 = self.conv_layer(self.conv5_2, "conv5_3")
        self.pool5 = self.max_pool(self.conv5_3, 'pool5')

        self.fc6 = self.fc_layer(self.pool5, "fc6")
        assert self.fc6.get_shape().as_list()[1:] == [4096], 'first shape of fully connected layer is not 4096'
        self.relu6 = tf.nn.relu(self.fc6)

        self.fc7 = self.fc_layer(self.relu6, "fc7")
        self.relu7 = tf.nn.relu(self.fc7)

        self.fc8 = self.fc_layer(self.relu7, "fc8")

        # softmax
        self.prob = tf.nn.softmax(self.fc8, name="prob")

        self.data_dict = None
        print(("build model finished: %ds" % (time.time() - start_time)))

    def avg_pool(self, bottom, name):
        # tf.nn.avg_pool(bottom, ksize=[1,2,2,1], strides=[1,2,2,1], padding='SAME', name=name)
        return tf.nn.avg_pool(bottom, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME', name=name)

    def max_pool(self, bottom, name):
        # notice: padding is 'SAME'
        return tf.nn.max_pool(bottom, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding='SAME', name=name)

    def conv_layer(self, bottom, name):
        # with tf.variable_scope(name):
        with tf.variable_scope(name):
            filt = self.get_conv_filter(name)

            # strides=[1,1,1,1], padding='SAME'
            conv = tf.nn.conv2d(bottom, filt, [1, 1, 1, 1], padding='SAME')

            conv_biases = self.get_bias(name)
            bias = tf.nn.bias_add(conv, conv_biases)

            relu = tf.nn.relu(bias)
            return relu

    def fc_layer(self, bottom, name):
        with tf.variable_scope(name):
            shape = bottom.get_shape().as_list() # 返回bottom的形状，然后转换为list
            dim = 1
            # 第0维是batch size
            for d in shape[1:]:
                dim *= d
            # x的shape为[batch_size, dim]
            x = tf.reshape(bottom, [-1, dim])

            weights = self.get_fc_weight(name)
            biases = self.get_bias(name)

            # Fully connected layer. Note that the '+' operation automatically
            # broadcasts the biases.
            fc = tf.nn.bias_add(tf.matmul(x, weights), biases)

            return fc

    # 从配置文件里获取filter
    def get_conv_filter(self, name):
        # 配置文件里有
        return tf.constant(self.data_dict[name][0], name="filter")

    def get_bias(self, name):
        return tf.constant(self.data_dict[name][1], name="biases")

    def get_fc_weight(self, name):
        return tf.constant(self.data_dict[name][0], name="weights")
