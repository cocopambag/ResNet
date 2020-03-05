import tensorflow as tf
import numpy as np
import datetime as dt

from tensorflow.keras.datasets.cifar10 import load_data
from tensorflow.keras.layers import BatchNormalization, Conv2D, Activation, Dense, GlobalAveragePooling2D,\
MaxPooling2D, ZeroPadding2D, Add, ZeroPadding3D
from tensorflow.keras import Model


## solve
from tensorflow.compat.v1 import ConfigProto
from tensorflow.compat.v1 import InteractiveSession

config = ConfigProto()
config.gpu_options.per_process_gpu_memory_fraction = 0.2
config.gpu_options.allow_growth = True
session = InteractiveSession(config=config)
## 
def dataset():
	'''
		Make Dataset.
		CIFAR-10 is trainset(50k) and testset(10k).
		Divide the trainset and make a validation set
		trainset(50k) = train(45k) + validation(5k)
	'''
	# Load CIFAR-10 
	(x_train, y_train), (x_test, y_test) = load_data()

	# # one_hot_encoding
	y_train = tf.one_hot(y_train, 10)
	y_test = tf.one_hot(y_test, 10)

	# 0~ 255 -> 0~1
	x_train = x_train / 255
	y_train = y_train / 255
	x_test = x_test / 255
	y_test = y_test / 255

	# Trainset(50k) -> train(45k) + validation(5k)
	x_val = x_train[-5000:] / 255
	y_val = y_train[-5000:] / 255

	return x_train[:45000], y_train[:45000], x_test, y_test, x_val, y_val
	

class Resnet():

	def __init__(self, number, name):
		'''
			number : The number of Residual Block
			name : Network name

			 _build_net() is building ResNet.
		'''
		self.name = name
		self.number = number
		self.m = tf.keras.Input(shape=(32,32,3))
		self._build_net()

	def _build_net(self):
		'''
			Building ResNet.

			image -> First conv layer -> 1st Residual block(2n) -> 2nd Residual block(2n) -> 3nd Residual block(2n)
			-> 10-fc(softmax)

			(32, 32, 3) -> (32, 32, 16) -> (32, 32, 16) -> (16, 16, 32) -> (8, 8, 64) -> (10)
		'''
		# input image (32, 32, 3)
		m = self.m
		
		# # First conv layer (32, 32, 3) -> (32, 32, 16)
		inputs = m
		m = Conv2D(filters=16, kernel_size=(3, 3), padding='same')(m)
		m = BatchNormalization()(m)
		m = Activation('relu')(m)
		outputs = m
		#self.prints(inputs,outputs,'First_conv')
		

		# First Residual Block ( 2n ) (32, 32, 16) -> (32, 32, 16)
		m, outputs = self.residual_block(m, self.number, 16, True)
		# self.prints(inputs,outputs,'First_residual_block')

		# Second Residual Block ( 2n ) (32, 32, 16) -> (16, 16, 32)
		m, outputs = self.residual_block(m, self.number, 32)
		#self.prints(inputs,outputs,'Second_residual_block')

		# Third Residual Block ( 2n ) (16, 16, 32) -> (8, 8, 64)
		m, outputs = self.residual_block(m, self.number, 64)
		#self.prints(inputs,outputs,'Third_residual_block')

		# Global Average pooling
		m = GlobalAveragePooling2D()(m)

		# 10-fc
		m = Dense(10, activation='softmax')(m)

		# Used to shape. Because we use 'sparse_categorical_crossentropy' loss function.
		# See here https://www.tensorflow.org/api_docs/python/tf/keras/losses/sparse_categorical_crossentropy
		# Original shape : (?, 10) -> (?, 10, 1)
		m = tf.expand_dims(m,axis=2)
		self.prints(inputs, m, 'Full')

		# Make keras.Model()
		self.model = Model(inputs, m, name='Resnet_'+str(2*self.number*3 + 2))

		return self.model

	def prints(self, inputs, outputs, name):
		'''
			using Model.summary()
			intputs : Input images
			outputs : Output of desired model
			name : Name of desired model 

			 The desired network blocks can also be used.
		'''

		# Model.summary()
		Model(inputs=inputs, outputs=outputs, name=name).summary()



	def residual_block(self, m, n, filter, first=False):
	
		if not first:
			m = MaxPooling2D((1,1),2)(m)

		for i in range(n):
	
			shortcut = m
			if not first and i == 0:
				shortcut = Conv2D(filters=filter, kernel_size=(1,1), padding='same')(shortcut)
				shortcut = BatchNormalization()(shortcut)
				print(shortcut)
			m = Conv2D(filters=filter, kernel_size=(3,3), padding='same')(m)
			m = BatchNormalization()(m)
			m = Activation('relu')(m)
			m = Conv2D(filters=filter, kernel_size=(3,3), padding='same')(m)
			m = BatchNormalization()(m)
			m = Add()([m,shortcut])
			m = Activation('relu')(m)

		outputs = m

		return m, outputs

	def compile(self, lr, decay, momentum):
		'''
			lr : Learning rate Schedule
			decay : Weight decay
			momentum : momentum
		'''
		return self.model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr, beta_1=momentum, decay=decay),loss='sparse_categorical_crossentropy',
			metrics=['acc'])

	def fit(self, x, y, epoch, batch_size, validation_data, val_step, callbacks):
		'''
			x : input image
			y : input labels
			epoch : total number of time(learning number)
			batch_size : batch size
			validation_data : validation data set
			val_step : validation step
			callbacks : callbacks function
		'''
		return self.model.fit(x, y, epochs=epoch, batch_size=batch_size, 
			validation_data=validation_data, validation_steps=val_step, callbacks=callbacks)

	def evaluate(self, x, y, batch_size=32):
		'''
			x : test image
			y : test label
			batch_size : batch size
		'''
		return self.model.evaluate(x, y, batch_size=batch_size)

# train parameter
logs = './log'
Iter = 64000
Batch_size = 64
Trainset = 45000
Epoch = int(Batch_size * Trainset / Iter)
model_size = 3 
callbacks = [
  # Write TensorBoard logs to `./logs` directory
  tf.keras.callbacks.TensorBoard(log_dir=logs, write_images=True),
  tf.keras.callbacks.ModelCheckpoint(filepath=logs),
]

# Adam parameter
lr = 0.01
decay = 0.0001
momentum = 0.9

# Learning rate Schedule
step = tf.Variable(0, trainable=False)
boundaries = [32000, 48000]
values = [0.1, 0.01, 0.001]
learning_rate_fn = tf.keras.optimizers.schedules.PiecewiseConstantDecay(
        boundaries, values)
lr = learning_rate_fn(step)

# Make Dataset
x_train, y_train, x_test, y_test, x_val, y_val = dataset()

# Make Model
model = Resnet(model_size, 'resnet')

# compiling
compiles = model.compile(lr, decay, momentum)

# training
# Iter 64k 
# Batch 64 -> Paper's batch is 128 with 2-gpu. Use 64 batch size because my gpu is 1.
# Trainset 45k
# Batch * Trainset / Iter  => 64 * 45000 / 64000 = 45epochs
fit = model.fit(x_train, y_train, Epoch, Batch_size, [x_val,y_val], 3, callbacks)

# Model evaluate
results = model.evaluate(x_test, y_test)
print('test loss, test acc: {}'.format(results))

