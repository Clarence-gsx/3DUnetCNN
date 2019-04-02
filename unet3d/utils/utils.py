import pickle
import os
import sys
import collections

import nibabel as nib
import numpy as np
from nilearn.image import new_img_like, resample_to_img

from .nilearn_custom_utils.nilearn_utils import crop_img_to, run_with_background_correction


def is_iterable(arg):
    return isinstance(arg, collections.Iterable) and not isinstance(arg, str)


def pickle_dump(item, out_file):
    with open(out_file, "wb") as opened_file:
        pickle.dump(item, opened_file)


def pickle_load(in_file):
    with open(in_file, "rb") as opened_file:
        return pickle.load(opened_file)


def get_affine(in_file):
    return read_image(in_file).affine


def read_image_files(image_files, image_shape=None, crop=None, label_indices=None, background_correction=False):
    """
    
    :param image_files: 
    :param image_shape: 
    :param crop: 
    :param use_nearest_for_last_file: If True, will use nearest neighbor interpolation for the last file. This is used
    because the last file may be the labels file. Using linear interpolation here would mess up the labels.
    :return: 
    """
    if label_indices is None:
        label_indices = []
    elif not isinstance(label_indices, collections.Iterable) or isinstance(label_indices, str):
        label_indices = [label_indices]
    image_list = list()
    for index, image_file in enumerate(image_files):
        if (label_indices is None and (index + 1) == len(image_files)) \
                or (label_indices is not None and index in label_indices):
            interpolation = "nearest"
        else:
            interpolation = "linear"
        image_list.append(read_image(image_file, image_shape=image_shape, crop=crop, interpolation=interpolation,
                                     background_correction=background_correction))

    return image_list


def read_image(in_file, image_shape=None, interpolation='linear', crop=None, background_correction=False):
    print("Reading: {0}".format(in_file))
    image = nib.load(os.path.abspath(in_file))
    image = fix_shape(image)
    if crop:
        image = crop_img_to(image, crop, copy=True)
    if image_shape:
        return resize(image, new_shape=image_shape, interpolation=interpolation,
                      background_correction=background_correction)
    else:
        return image


def fix_shape(image):
    if image.shape[-1] == 1:
        return image.__class__(dataobj=np.squeeze(image.get_data()), affine=image.affine)
    return image


def resize(image, new_shape, interpolation="linear", background_correction=False, pad_mode='edge'):
    if background_correction:
        return run_with_background_correction(resize, image, new_shape=new_shape, interpolation=interpolation,
                                              background_correction=False)
    else:
        zoom_level = np.divide(new_shape, image.shape)
        new_spacing = np.divide(image.header.get_zooms()[:3], zoom_level)
        new_data = np.zeros(new_shape)
        new_affine = adjust_affine_spacing(np.copy(image.affine), new_spacing)
        new_img = new_img_like(image, new_data, affine=new_affine)
        return resample_image(image, new_img, interpolation=interpolation, pad_mode=pad_mode,
                              pad=np.any(np.greater(new_shape, image.shape)))


def adjust_affine_spacing(affine, new_spacing, spacing=None):
    if spacing is None:
        spacing = get_spacing_from_affine(affine)
    offset = calculate_origin_offset(new_spacing, spacing)
    new_affine = np.copy(affine)
    translation_affine = np.diag(np.ones(4))
    translation_affine[:3, 3] = offset
    new_affine = np.matmul(new_affine, translation_affine)
    new_affine = set_affine_spacing(new_affine, new_spacing)
    return new_affine


def resample_image_to_spacing(image, new_spacing, interpolation='continuous'):
    new_affine = adjust_affine_spacing(image.affine, new_spacing, spacing=image.header.get_zooms()[:3])
    new_shape = np.asarray(np.ceil(np.divide(get_extent_from_image(image), new_spacing)), dtype=np.int)
    new_data = np.zeros(new_shape)
    new_image = new_img_like(image, new_data, affine=new_affine)
    return resample_to_img(image, new_image, interpolation=interpolation)


def resample_image(source_image, target_image, interpolation="linear", pad_mode='edge', pad=False):
    if pad:
        source_image = pad_image(source_image, mode=pad_mode)
    return resample_to_img(source_image, target_image, interpolation=interpolation)


def pad_image(image, mode='edge', pad_width=1):
    affine = np.copy(image.affine)
    spacing = np.copy(image.header.get_zooms()[:3])
    affine[:3, 3] -= spacing * pad_width
    if len(image.shape) > 3:
        # just pad the first three dimensions
        pad_width = [[pad_width]*2]*3 + [[0, 0]]*(len(image.shape) - 3)
    data = np.pad(image.get_data(), pad_width=pad_width, mode=mode)
    return image.__class__(data, affine)


def calculate_origin_offset(new_spacing, old_spacing):
    return np.divide(np.subtract(new_spacing, old_spacing)/2, old_spacing)


def resize_affine(affine, shape, target_shape, copy=True):
    if copy:
        affine = np.copy(affine)
    scale = np.divide(shape, target_shape)
    spacing = get_spacing_from_affine(affine)
    target_spacing = np.multiply(spacing, scale)
    affine = adjust_affine_spacing(affine, target_spacing)
    return affine


def get_spacing_from_affine(affine):
    RZS = affine[:3, :3]
    return np.sqrt(np.sum(RZS * RZS, axis=0))


def set_affine_spacing(affine, spacing):
    scale = np.divide(spacing, get_spacing_from_affine(affine))
    affine_transform = np.diag(np.ones(4))
    np.fill_diagonal(affine_transform, list(scale) + [1])
    return np.matmul(affine, affine_transform)


def resample(image, target_affine, target_shape, interpolation='linear', pad_mode='edge', pad=False):
    target_data = np.zeros(target_shape)
    target_image = image.__class__(target_data, affine=target_affine)
    return resample_image(image, target_image, interpolation=interpolation, pad_mode=pad_mode, pad=pad)


def update_progress(progress, bar_length=30, message=""):
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(bar_length * progress))
    text = "\r{0}[{1}] {2:.2f}% {3}".format(message, "#" * block + "-" * (bar_length - block), progress*100, status)
    sys.stdout.write(text)
    sys.stdout.flush()


def copy_image(image):
    return image.__class__(np.copy(image.get_data()), image.affine)


def get_extent_from_image(image):
    return np.multiply(image.shape[:3], image.header.get_zooms()[:3])
