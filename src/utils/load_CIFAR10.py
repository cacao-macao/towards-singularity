import numpy as np
import os
import pickle


def load_data(ROOT):
    """ Load all of CIFAR-10. """
    xs = []
    ys = []

    # The archive contains the files data_batch_1, ..., data_batch_5, as well as test_batch
    # Each of these files is a Python "pickled" object
    for _batch in range(1,6):
        with open(os.path.join(ROOT, "data_batch_%d" % (_batch)), "rb") as file:
            datadict = pickle.load(file, encoding="latin1")
            # Loaded in this way, each of the batch files contains a dictionary with the following elements:
            # - data - a 10000x3072 numpy array. Each row of the array stores a 32x32 color image. The first
            #          1024 entries contain the red channel values, the next 1024 the green, and the final
            #          1024 the blue. The image is stored in a row-major order, so that the first 32 entries
            #          of the array are the red channel values of the first row of the image
            # - labels - a list of 10000 numbers in the range 0-9. The number at index i indicates the label
            #            of the i-th image in the array data
            X = datadict["data"]
            Y = datadict["labels"]
            X = X.reshape(10000, 3, 32, 32).transpose(0,2,3,1).astype("float")
            Y = np.array(Y)
        xs.append(X)
        ys.append(Y)
    X_train = np.concatenate(xs)
    y_train = np.concatenate(ys)
    del X, Y

    # The test batch contains exactly 1000 randomly selected images from each class
    with open(os.path.join(ROOT, "test_batch"), "rb") as file:
        datadict = pickle.load(file, encoding="latin1")
        X_test = datadict["data"]
        y_test = datadict["labels"]
        X_test = X_test.reshape(10000, 3, 32, 32).transpose(0,2,3,1).astype("float")
        y_test = np.array(y_test)

    # The dataset contains another file, called batches.meta. It too contains a Python dictionary object.
    # It has the following entry:
    # - label_names - a 10-element list which gives meaningful names to the numeric labels
    with open(os.path.join(ROOT, "batches.meta"), "rb") as file:
        datadict = pickle.load(file, encoding="latin1")
        classes = np.array(datadict["label_names"])

    return X_train, y_train, X_test, y_test, classes


def get_CIFAR10_data(ROOT, num_training=49000, num_validation=1000, num_test=1000,
                     zero_center=True, normalize=False, whiten=False):
    """
    Load the CIFAR-10 dataset from disk and perform preprocessing to prepare
    it for classifiers.
    """
    # Load the raw CIFAR-10 data
    X_train, y_train, X_test, y_test, classes = load_data(ROOT)

    # Subsample the data
    mask = list(range(num_training, num_training + num_validation))
    X_val = X_train[mask]
    y_val = y_train[mask]
    mask = list(range(num_training))
    X_train = X_train[mask]
    y_train = y_train[mask]
    mask = list(range(num_test))
    X_test = X_test[mask]
    y_test = y_test[mask]

    # Zero-center the data: subtract the mean image
    if zero_center:
        mean_image = np.mean(X_train, axis=0)
        X_train -= mean_image
        X_val -= mean_image
        X_test -= mean_image

    # Normalize the data.
    if normalize:
        std = np.std(X_train, axis=0)
        X_train /= std
        X_val /= std
        X_test /= std

    # Transpose so that channels come first.
    X_train = X_train.transpose(0, 3, 1, 2).copy()
    X_val = X_val.transpose(0, 3, 1, 2).copy()
    X_test = X_test.transpose(0, 3, 1, 2).copy()

    # Package data into a dictionary.
    data = {"X_train":X_train, "y_train":y_train,
            "X_val":X_val, "y_val":y_val,
            "X_test":X_test, "y_test":y_test,
            "classes":classes}

    return data

#