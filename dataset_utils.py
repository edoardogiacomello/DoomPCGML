import networkx as nx
from collections import namedtuple
from collections import defaultdict
import os
from PIL import Image
import numpy as np
import json
import tensorflow as tf
from scipy import misc


# This part contains all the variables concerning the dataset
# This is the tile dictionary, containing also the pixel colors for image conversion
encoding_interval = (255 // 16)
tile_tuple = namedtuple("tile_tuple", ["pixel_color", "tags"])
tiles_greyscale = {
        "-": tile_tuple(( 0), ["empty", "out of bounds"]),  # is black
        "X": tile_tuple((1 * encoding_interval), ["solid", "wall"]),  # maroon
        ".": tile_tuple((2 * encoding_interval), ["floor", "walkable"]), # coral
        ",": tile_tuple((3 * encoding_interval), ["floor", "walkable", "stairs"]), # Beige
        "E": tile_tuple((4 * encoding_interval), ["enemy", "walkable"]), # red
        "W": tile_tuple((5 * encoding_interval), ["weapon", "walkable"]), # Blue
        "A": tile_tuple((6 * encoding_interval), ["ammo", "walkable"]), # Cyan
        "H": tile_tuple((7 * encoding_interval), ["health", "armor", "walkable"]), # Green
        "B": tile_tuple((8 * encoding_interval), ["explosive barrel", "walkable"]), # Magenta
        "K": tile_tuple((9 * encoding_interval), ["key", "walkable"]), # Teal
        "<": tile_tuple((10 * encoding_interval), ["start", "walkable"]), # Lavender
        "T": tile_tuple((11 * encoding_interval), ["teleport", "walkable", "destination"]), # Olive
        ":": tile_tuple((12 * encoding_interval), ["decorative", "walkable"]), # Grey
        "L": tile_tuple((13 * encoding_interval), ["door", "locked"]), # Brown
        "t": tile_tuple((14 * encoding_interval), ["teleport", "source", "activatable"]), # Mint
        "+": tile_tuple((15 * encoding_interval), ["door", "walkable", "activatable"]), # Orange
        ">": tile_tuple((16 * encoding_interval), ["exit", "activatable"]) # White
    }

tiles = {
        "-": tile_tuple((0,   0,   0), ["empty", "out of bounds"]),  # is black
        "X": tile_tuple((128, 0,   0), ["solid", "wall"]),  # maroon
        ".": tile_tuple((255, 215, 180), ["floor", "walkable"]), # coral
        ",": tile_tuple((255, 250, 200)	, ["floor", "walkable", "stairs"]), # Beige
        "E": tile_tuple((230, 25,  75), ["enemy", "walkable"]), # red
        "W": tile_tuple((0,   130, 200), ["weapon", "walkable"]), # Blue
        "A": tile_tuple((70,  240, 240)	, ["ammo", "walkable"]), # Cyan
        "H": tile_tuple((60,  180, 75), ["health", "armor", "walkable"]), # Green
        "B": tile_tuple((240, 50,  230), ["explosive barrel", "walkable"]), # Magenta
        "K": tile_tuple((0,   128, 128), ["key", "walkable"]), # Teal
        "<": tile_tuple((230, 190, 255)	, ["start", "walkable"]), # Lavender
        "T": tile_tuple((128, 128, 0), ["teleport", "walkable", "destination"]), # Olive
        ":": tile_tuple((128, 128, 128)	, ["decorative", "walkable"]), # Grey
        "L": tile_tuple((170, 110, 40)	, ["door", "locked"]), # Brown
        "t": tile_tuple((170, 255, 195)	, ["teleport", "source", "activatable"]), # Mint
        "+": tile_tuple((245, 130, 48)	, ["door", "walkable", "activatable"]), # Orange
        ">": tile_tuple((255, 255, 255)	, ["exit", "activatable"]) # White
    }


grey_to_rgb = [
[0,   0,   0], 
[128, 0,   0], 
[255, 215, 180],
[255, 250, 200],
[230, 25,  75],
[0,   130, 200],
[70,  240, 240],
[60,  180, 75],
[240, 50,  230],
[0,   128, 128],
[230, 190, 255],
[128, 128, 0], 
[128, 128, 128],
[170, 110, 40],	
[170, 255, 195],
[245, 130, 48],	
[255, 255, 255]]



def tf_from_grayscale_to_tilespace(images):
    """
    Converts a batch of inputs from the floating point representation [0,1] to the tilespace representation [0,1,..,n_tiles]
    :param images:
    :return:
    """
    # Rescale the input to [0,255]
    rescaled = images * tf.constant(255.0, dtype=tf.float32)
    interval = tf.constant(encoding_interval, dtype=tf.float32)
    half_interval = tf.constant(encoding_interval / 2, dtype=tf.float32)
    # Here the image has pixel values that does not correspond to anything in the encoding
    mod = tf.mod(rescaled, interval)  # this is the error calculated from the previous right value.
    # I.e. if the encoding is [0, 15, 30] and the generated value is [14.0, 16.0, 30.0] this is [14, 1, 0]
    div = tf.floor_div(rescaled, interval)
    # this is the encoded value if the error is less then half the sampling interval, right_value - 1 otherwise
    # E.g. (continuing the example) [0, 1, 2] while the correct encoding should be [1, 1, 2]
    mask = tf.floor(tf.divide(mod, half_interval))
    #  This mask tells which pixels are already right (0) or have to be incremented (1)
    # E.g [1, 0, 0]
    encoded = div + mask  # Since the mask can be either 0 or 1 for each pixel, the true encoding
    # will be obtained by summing the two
    return encoded

def tf_from_grayscale_to_rgb(tile_indices):
    """
    Converts a greyscale sample (encoded by tiles_greyscale) to a rgb image (encoded by tiles dict) for better
    visualization
    :param tile_indices: a Tensor with shape [batch, height, width, 1]
    :return: a Tensor with shape [batch, height, width, 3]
    """
    palette = tf.constant(grey_to_rgb, dtype=tf.float32)
    return tf.squeeze(tf.gather(palette, tf.to_int32(tile_indices)), axis=3)

def tf_from_grayscale_to_multichannel(images):
    """
    Converts a batch of images from a greyscale (0,1) representation to a space [batch, height, width, n_tiles] where
    each channel represent a type of tile, and the data can be either 0 or 1.
    :param tile_indices:
    :return:
    """
    encoded = tf.to_int32(tf_from_grayscale_to_tilespace(images))
    return tf.squeeze(tf.one_hot(encoded, depth=len(tiles_greyscale)), axis=3)

def tf_match_encoding(gen_output):
    """
    Correct the encoding of a noisy sample generated by the network
    :param gen_output:
    :return: An image batch of float in (0,1) which assume only n_tile values
    """
    g_encoded = tf_from_grayscale_to_tilespace(gen_output)
    # g_encoded contains the sample in label space (0 to n_tiles),
    # it has to be converted to be consistent with the true samples
    # Scaling to [0,1]
    return tf.multiply(g_encoded, tf.constant(255 // 16, dtype=tf.float32)) / tf.constant(255, dtype=tf.float32)


    

class DatasetManager(object):
    """Extract metadata from the tile/grid representation of a level"""
    def __init__(self, path_to_WADs_folder='./WADs', relative_to_json_files=[], target_size=(512,512), target_channels=1):
        """
        Utility class for extracting metadata from the tile/grid representation, representation conversion (e.g to PNG)
        and TFRecord conversion an loading.

        :param path_to_WADs_folder: path to the /WADs/ folder when converting a dataset
        :param relative_to_json_files: list of paths to the json databases from the wad folder. eg: ['doom/Doom.json']
        :param target_size: Final (for conversion) or expected (for TFRecord loading) sample size in PNG/tile format.
        """
        self.G = nx.DiGraph()
        self.json_files = relative_to_json_files
        self.root = path_to_WADs_folder
        self.target_size = target_size
        self.target_channels = target_channels

    def _get_absolute_path(self, relative_path):
        """
        Given a relative path of type: "./WADs/....." returns the absolute path considering the root specified in init
        :param relative_path:
        :return:
        """
        # since tile_path begins with './WADs/'" we prepend our root
        if relative_path.startswith('./WADs/'):
            return relative_path.replace('./WADs/', self.root)
        else:
            return relative_path.replace('./', self.root)

    def extract_size(self):
        """For every level listed into the json files, adds the 'height' and 'width' information"""
        for j in self.json_files:
            with open(self.root + j, 'r') as jin:
                levels = json.load(jin)
            for level in levels:
                tile_path = self._get_absolute_path(level['tile_path'])
                # Open the tile file
                with open(tile_path) as level_file:
                    lines = [line.strip() for line in level_file.readlines()]
                    level['height'] = len(lines)
                    level['width'] = len(lines[0])
            with open(self.root+j+'.updt', 'w') as jout:
                json.dump(levels, jout)

    def _grid_to_matrix(self):
        pass

    def _grid_to_image(self, path):
        """
        Convert (renders) a tile representation of a level to a PNG
        :param path: Path of the .txt file
        :return: Pillow Image object
        """
        with open(path, 'r') as tilefile:
            lines = [line.strip() for line in tilefile.readlines()]
        n_lines = len(lines)
        n_cols = len(lines[0])
        mode = 'L' if self.target_channels == 1 else 'RGB'
        tile_set = tiles_greyscale if self.target_channels == 1 else tiles

        img = Image.new(mode, (n_lines, n_cols), "black")  # create a new black image

        ip = 0  # pixel counters
        jp = 0
        for i in lines:  # for every tile:
            for j in i:
                c = tile_set[j].pixel_color
                img.putpixel((ip, jp), c)
                jp += 1
            jp = 0
            ip += 1
        return img

    def convert_to_images(self):
        """
        For every level listed in the json databases, creates an image render from the grid/tile representation of the level
        and saves it into the /<gamename>/Processed - Rendered/ folder.
        It also updates the json database with img_path, width and height columns
        :return: None
        """
        for j in self.json_files:
            with open(self.root + j, 'r') as jin:
                levels = json.load(jin)
            for level in levels:
                tile_path = self._get_absolute_path(level['tile_path'])
                # We change to the Image subfolder
                img_path = tile_path.replace('Processed', 'Processed - Rendered').replace('.txt','.png')
                img_folder = '/'.join(img_path.split('/')[:-1])+'/'

                if not os.path.exists(img_folder):
                    os.makedirs(img_folder)
                img = self._grid_to_image(tile_path)
                img.save(img_path, 'PNG')
                # Update the json file with the new path
                # [img_path contains the new root so it may be not consistent with the other paths already in db]
                level['img_path'] = level['tile_path'].replace('Processed', 'Processed - Rendered').replace('.txt','.png')
                # Also update the level size
                level['width'] = img.size[0]
                level['height'] = img.size[1]
            with open(self.root + j, 'w') as jout:
                json.dump(levels, jout)


    def _sample_to_TFRecord(self, json_record, image):
        # converting the record to a default_dict since it may does not contain some keys for empty values.
        json_record = defaultdict(lambda: "", json_record)
        features = {
            'author': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['author'])])),
            'description': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['description'])])),
            'credits': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['credits'])])),
            'base': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['base'])])),
            'editor_used': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['editor_used'])])),
            'bugs': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['bugs'])])),
            'build_time': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['build_time'])])),
            'creation_date': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['creation_date'])])),
            'file_url': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['file_url'])])),
            'game': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['game'])])),
            'category': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['category'])])),
            'title': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['title'])])),
            'name': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['name'])])),
            'path': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['path'])])),
            'svg_path': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['svg_path'])])),
            'tile_path': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['tile_path'])])),
            'img_path': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(json_record['img_path'])])),
            'page_visits': tf.train.Feature(int64_list=tf.train.Int64List(value=[int(json_record['page_visits'])])),
            'downloads': tf.train.Feature(int64_list=tf.train.Int64List(value=[int(json_record['downloads'])])),
            'height': tf.train.Feature(int64_list=tf.train.Int64List(value=[int(json_record['height'])])),
            'width': tf.train.Feature(int64_list=tf.train.Int64List(value=[int(json_record['width'])])),
            'rating_count': tf.train.Feature(int64_list=tf.train.Int64List(value=[int(json_record['rating_count'])])),
            'rating_value': tf.train.Feature(float_list=tf.train.FloatList(value=[float(json_record['rating_value'])])),
            'image': tf.train.Feature(bytes_list=tf.train.BytesList(value=[image.tobytes()]))
        }

        return tf.train.Example(features=tf.train.Features(feature=features))

    def _TFRecord_to_sample(self, TFRecord):
        features = {
            'author': tf.FixedLenFeature([],tf.string),
            'description': tf.FixedLenFeature([],tf.string),
            'credits': tf.FixedLenFeature([],tf.string),
            'base': tf.FixedLenFeature([],tf.string),
            'editor_used': tf.FixedLenFeature([],tf.string),
            'bugs': tf.FixedLenFeature([],tf.string),
            'build_time': tf.FixedLenFeature([],tf.string),
            'creation_date': tf.FixedLenFeature([],tf.string),
            'file_url': tf.FixedLenFeature([],tf.string),
            'game': tf.FixedLenFeature([],tf.string),
            'category': tf.FixedLenFeature([],tf.string),
            'title': tf.FixedLenFeature([],tf.string),
            'name': tf.FixedLenFeature([],tf.string),
            'path': tf.FixedLenFeature([],tf.string),
            'svg_path': tf.FixedLenFeature([],tf.string),
            'tile_path': tf.FixedLenFeature([],tf.string),
            'img_path': tf.FixedLenFeature([],tf.string),
            'page_visits': tf.FixedLenFeature([],tf.int64),
            'downloads': tf.FixedLenFeature([],tf.int64),
            'height': tf.FixedLenFeature([],tf.int64),
            'width': tf.FixedLenFeature([],tf.int64),
            'rating_count': tf.FixedLenFeature([],tf.int64),
            'rating_value': tf.FixedLenFeature([],tf.float32),
            'image': tf.FixedLenFeature([],tf.string)
        }

        parsed_features = tf.parse_single_example(TFRecord, features)
        parsed_img = tf.decode_raw(parsed_features['image'], tf.uint8)
        parsed_img = tf.reshape(parsed_img, shape=(self.target_size[0], self.target_size[1], self.target_channels) )
        parsed_features['image'] = parsed_img
        return parsed_features


    def _pad_image(self, image):
        """Center pads an image, adding a black border up to "target size" """
        assert image.shape[0] <= self.target_size[0], "The image to pad is bigger than the target size"
        assert image.shape[1] <= self.target_size[1], "The image to pad is bigger than the target size"
        padded = np.zeros((self.target_size[0],self.target_size[1],self.target_channels), dtype=np.uint8)
        offset = (self.target_size[0] - image.shape[0])//2, (self.target_size[1] - image.shape[1])//2  # Top, Left
        padded[offset[0]:offset[0]+image.shape[0], offset[1]:offset[1]+image.shape[1],:] = image
        return padded


    def convert_to_TFRecords(self, output_path, exclude_tiny_levels=True):
        """
        Pack the whole image dataset into the TFRecord standardized format and saves it at the specified output path.
        Pads each sample to the target size, DISCARDING the samples that are larger (this behaviour may change in future).
        Information about image size has to be stored separately.
        :return: None.
        """
        # Load the json files
        levels = []
        for j in self.json_files:
            with open(self.root + j, 'r') as jin:
                levels += json.load(jin)
        print("{} levels loaded.".format(len(levels)))
        with tf.python_io.TFRecordWriter(output_path) as writer:
            counter = 0
            saved_levels = 0
            for level in levels:
                counter += 1
                too_big = int(level['width']) > self.target_size[1] or int(level['height']) > self.target_size[0]
                is_tiny = int(level['width']) < 16 or int(level['height']) < 16 if exclude_tiny_levels else False
                if too_big or is_tiny:
                    continue
                mode = 'L' if self.target_channels == 1 else 'RGB'
                image = misc.imread(self._get_absolute_path(level['img_path']), mode=mode)
                if self.target_channels == 1:
                    image = np.expand_dims(image,-1)
                padded = self._pad_image(image)
                sample = self._sample_to_TFRecord(level, padded)
                writer.write(sample.SerializeToString())
                saved_levels+=1
                if counter % (len(levels)//100) == 0:
                    print("{}% completed.".format(round(counter/len(levels)*100)))
            print("Levels saved: {}, levels discarded: {}".format(saved_levels, len(levels)-saved_levels))
    def load_TFRecords_database(self, path):
        """Returns a tensorflow dataset from the .tfrecord file specified in path"""
        dataset = tf.contrib.data.TFRecordDataset(path)
        dataset = dataset.map(self._TFRecord_to_sample, num_threads=9)
        return dataset

def generate_images_and_convert():
    shapes = [64, 128, 256, 512]
    # Convert every image to greyscale
    # dmm_grey = DatasetManager('/run/media/edoardo/BACKUP/Datasets/DoomDataset/WADs/',
    #                     ['Doom/Doom.json', 'DoomII/DoomII.json'], target_channels=1)
    # dmm_grey.convert_to_images()
    # Save a dataset for each dimension
    for shape in shapes:
        dmm = DatasetManager('/run/media/edoardo/BACKUP/Datasets/DoomDataset/WADs/',
                             ['Doom/Doom.json', 'DoomII/DoomII.json'],
                             target_size=(shape, shape), target_channels=1)
        dmm.convert_to_TFRecords('/run/media/edoardo/BACKUP/Datasets/DoomDataset/lessthan{}_tilespace.TFRecords'.format(shape))

# [scrapeUtils.json_to_csv(j) for j in ['/run/media/edoardo/BACKUP/Datasets/DoomDataset/WADs/Doom/Doom.json.updt', '/run/media/edoardo/BACKUP/Datasets/DoomDataset/WADs/DoomII/DoomII.json.updt']]
