import librosa
import numpy as np
from glob import glob
import argparse
from concurrent.futures import ProcessPoolExecutor
import os
from tqdm import tqdm
from root.common.hparams import params
from itertools import chain
import matplotlib
import matplotlib.pyplot as plt
# matplotlib.use('GTK')

# sample the data into bit rate
scale_factor = int(2**(params.bit_rate_in_power-1))

# divmod the data into bit_rate/2
split_factor = int(2**(params.bit_rate_in_power/2))

# resample the coarse and fine into (-1,1)
second_split = int(2**(params.bit_rate_in_power/2-1))

# filter bank
filter_bank = librosa.filters.mel(sr=params.sample_rate,
                                  n_fft=params.nFft,
                                  n_mels=params.num_mels,
                                  fmin=params.fmin,
                                  fmax=params.fmax)


def sample_data(linear):

    bit_16_signal = scale_factor*(linear+1)
    coarse_linear, fine_linear = np.divmod(bit_16_signal, split_factor)

    padded_coarse = np.insert((coarse_linear/second_split - 1)[:-1], 0, 0)
    padded_fine = np.insert((fine_linear/second_split - 1)[:-1], 0, 0)

    pad_input = np.stack([padded_coarse, padded_fine], axis=0)
    ground_truth = np.stack([coarse_linear, fine_linear], axis=0)

    return (pad_input, ground_truth)


def import_data(file_name):

    return librosa.core.load(file_name)[0]


def mel_spectogram(data, filter_bank):
    Fd = librosa.core.stft(data, n_fft=params.nFft, hop_length=params.hop_size)
    mel = np.dot(filter_bank, np.abs(Fd))
    mel_in_db = librosa.core.amplitude_to_db(mel, top_db=params.max_db)
    normalized = (mel_in_db+params.max_db)/params.max_db
    return normalized


def process_individual_file(input_file_uri, index):

    data = import_data(input_file_uri)

    mfcc = mel_spectogram(data, filter_bank)

    mfcc_shape = mfcc.shape
    num_elem_in_mfcc = mfcc_shape[0]*mfcc_shape[1]
    pad_val = params.scale_factor*num_elem_in_mfcc - data.shape[0]
    data = np.pad(data, [0, pad_val], mode="constant")
    assert data.shape[0] % num_elem_in_mfcc == 0

    inpt, gt = sample_data(data)

    output_file_uri = os.path.join(
        training_data_folder, "sample_{}".format(index))
    np.savez_compressed(output_file_uri, input=inpt, ground_truth=gt)

    return None


def preprocess(input_folders):
    concurrent_executor = ProcessPoolExecutor(
        max_workers=params.num_of_workers)

    source_files = list(chain.from_iterable([glob(source_folder+"/*.wav")
                                             for source_folder in input_folders]))

    indices = np.arange(len(source_files))

    for e in tqdm(concurrent_executor.map(process_individual_file, source_files, indices)):
        continue


def main():
    """
        We used preprocess.py to reduce training time by pre loading
        and manipulating speech files into faster numpy arrays.

        Read readme.md for support and details.
    """

    global training_data_folder
    training_data_folder = params.train_data_dir
    os.makedirs(training_data_folder, exist_ok=True)
    input_folders = params.input_data_dirs

    preprocess(input_folders)
