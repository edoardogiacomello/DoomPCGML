import json
import os
import csv
import WAD_Parser.Dictionaries.Features as Features
import numpy as np

class DoomDataset():
    """
    Utility class for loading and managing the doom dataset in .json/png representation.
    The dataset is structured as follow:
    - a root <dataset_root>/
    - a .json database <dataset_root>/dataset.json in which all the level features are stored
    - a <dataset_root>/Original/ folder, containing the .WAD files for each level
    - a <dataset_root>/Processed/ folder, containing:
        -<zip_name>_<wad_name>_<slot_name>.json file containing the features for a level (one row dataset.json)
        -<zip_name>_<wad_name>_<slot_name>_<feature_map>.png image(s) containing the feature map for a level

    These files are indexed from the dataset.json starting from <dataset_root>.
    E.g. a path could be "Processed/myzip_MyLevel_E1M1_floormap.png"
    The feature maps dimensions are (width/32, height/32), since 32 is the diameter of the smallest thing that exists on Doom.
    Each pixel value is an uint8, dicrectly encoding a value (ie. the "thing type index" for thingsmap; 1,2,3,4.. for
    the "floormap" enumeration or the floor_height value for the heightmap.

    Dataset can also be stored in a .TFRecord file (and this is the format DoomGAN uses to read the dataset);
    this is useful if you want to previously filter a dataset perhaps selecting only <128x128 levels and padding smaller ones.
    This way you pack all the dataset in a single .TFRecord file and its relative .meta file, containing aggregated data
    for each feature, such as min/max/avg value along the samples that have been selected in order to further normalize the data.
    """
    def __init__(self):
        self.root = None  # Root when reading from json
        self.json_db = None

    def read_from_json(self, json_db):
        """
        Reads the db from it's .json database and returns a list of level records.
        :param json_db: the .json file record in <dataset_root>/<yourdb>.json
        :return:
        """
        assert os.path.isfile(json_db), "Json database not found at {}".format(json_db)
        self.json_db = json_db
        self.root = '/'.join(json_db.split('/')[0:-1]) + '/'
        assert os.path.isdir(self.root+'Processed/'), '"Processed" directory not found in {}'.format(self.root)
        assert os.path.isdir(self.root+'Original/'), '"Processed" directory not found in {}'.format(self.root)
        levels = list()
        with open(json_db, 'r') as fin:
            levels += json.load(fin)
        return levels

    def get_path_of(self, feature_field):
        """
        Return the full path for a given feature, such a featuremap.
         Example: .get_path_of(level["wallmap"]) = /path/to/root/Processed/yourlevel_wallmap.png
        :param feature: The field containing the relative path of the featuremap/wad file you want to obtain
        :return: A file path
        """
        assert self.root is not None, "No root specified for this database. Are you sure you opened it with read_from_json()?"
        return self.root+feature_field

    def rebuild_database(self, root, database_name='database.json'):
        """
        Reads all the .json files inside the given <root>/"Processed" folder and rebuilds the database
        :param root: The root folder of the database. All the <level>.json and <level>.png must be stored into the "Processed" subfolder
        :param database_name: Filename of the resulting file. It will be saved to <root>/<database_name>
        :return:
        """
        import glob
        assert os.path.isdir(root + 'Processed/'), '"Processed" directory not found in {}'.format(self.root)
        self.root = root
        processed_folder = self.root+'Processed/'
        jsons = glob.glob(processed_folder + '*.json')
        database = list()
        for i, j in enumerate(jsons):
            with open(j, 'r') as jin:
                database += [json.load(jin)]
            if i % 100 == 0:
                print("{} of {} records rebuilt".format(i, len(jsons)))
        with open(self.root+database_name, 'w') as jout:
            json.dump(database, jout)

    def read_meta(self, tfrecord_path):
        meta_path = tfrecord_path + '.meta'
        assert os.path.isfile(meta_path), \
            ".meta file database not found at {}. No dataset statistics for normalizing the data".format(meta_path)
        with open(meta_path, 'r') as meta_in:
            return json.load(meta_in)

    def get_dataset_count(self, tfrecord_path):
        return self.read_meta(tfrecord_path)['count']

    def recompute_features(self, root, old_json_db, new_json_db):
        """
        This functions gets a json database and re-computes all the features and the maps for each WAD referenced by it,
        parsing all the WAD files from scratch. Useful when you are adding or editing features.
        WARNING: This function may overwrite your data, so make sure to keep a backup before executing it.
        :param root:
        :param old_json_db:
        :param new_json_db:
        :return:
        """
        import itertools
        import WAD_Parser.WADEditor as we
        import warnings
        old_records = self.read_from_json(old_json_db)
        print("Sorting levels..")
        sorted_input = sorted(old_records, key=lambda x: x['path'])
        # Grouping the old levels by .WAD path

        wad_records = itertools.groupby(sorted_input, key=lambda x: x['path'])
        new_records = list()
        for i, (wad, record) in enumerate(wad_records):
            # Assuming that wad-level features are the same for each level
            record = next(record)
            wad_reader = we.WADReader()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    parsed_wad = wad_reader.extract(wad_fp=root+record['path'], save_to=root+'Processed/', update_record=record,
                                                root_path=root)
                except:
                    print("Error parsing {}".format(root+record['path']))
            for level in parsed_wad['levels']:
                new_records.append(level['features'])
            if len(new_records) % (len(sorted_input)//100) == 0:
                print("{}% completed...".format(len(new_records)//(len(sorted_input)//100)))

        with open(new_json_db, 'w') as json_out:
            json.dump(new_records, json_out)
        print("Saved {} levels to {}".format(len(new_records), new_json_db))

    def to_csv(self, json_db_path, csv_path):
        """Converts a json dataset into csv representation, based on Features described in Features.py"""
        levels = self.read_from_json(json_db_path)
        with open(csv_path, 'w') as csvfile:
            keys = Features.features.keys()
            dict_writer = csv.DictWriter(csvfile, keys)
            dict_writer.writeheader()
            dict_writer.writerows(levels)
        print("Csv saved to: {}".format(csv_path))

    def filter_data(self, data, list_of_lambdas):
        for condition in list_of_lambdas:
            data = filter(condition, data)
        return list(data)


    def plot_joint_feature_distributions(self, path_or_data, features, cluster = False):
        """
        Plots the joint distribution for each couple of given feature
        :param path_or_data: (str or list) path of the json_db or the list of record containing data
        :param features: list of features to plot
        :return: None
        """
        import pandas as pd
        import seaborn as sb
        import matplotlib.pyplot as plt
        from sklearn import decomposition
        from sklearn import mixture
        data = self.read_from_json(path_or_data) if isinstance(path_or_data, str) else path_or_data
        points = np.array([[d[f] for f in features] for d in data])
        X=points
        if cluster:
            from sklearn.cluster import DBSCAN
            Y = DBSCAN(eps=0.3, min_samples=300).fit_predict(X)
            X = np.concatenate((X, np.expand_dims(Y, axis=-1)), axis=-1)
            # TODO: go on clustering
            # Plotting
            pd_dataset = pd.DataFrame(X, columns=features+['label'])
            g = sb.pairplot(pd_dataset, hue='label', plot_kws={"s": 10})
        else:
            pd_dataset = pd.DataFrame(X, columns=features)
            g = sb.pairplot(pd_dataset, plot_kws={"s": 10})
        return g

    def generate_stats(self):
        dataset = DoomDataset()
        # TODO: Remove this absolute path
        data = dataset.read_from_json('/run/media/edoardo/BACKUP/Datasets/DoomDataset/dataset.json')
        size_filter = lambda l: l['height']/32 <= 128 and l['width']/32 <= 128
        bound_things_number = lambda l: l['number_of_things'] < 1000 # Remove a few sample with a huge number of items
        bound_lines_per_sector = lambda l: l['lines_per_sector_avg'] < 150  # Removes a few samples with too many lines per sector
        bound_euler_number = lambda l: l['level_euler_number'] > -50  # Remove a few samples with too many holes

        data = dataset.filter_data(data, [size_filter,bound_things_number,bound_lines_per_sector,bound_euler_number])

        base_features = ['lines_per_sector_avg', 'number_of_things', 'walkable_area', 'walkable_percentage']
        level_features = [f for f in Features.features if f.startswith('level_') and not '_hu_' in f]
        floor_features = [f for f in Features.features if f.startswith('floors_') and (f.endswith('_mean'))]
        dataset.plot_joint_feature_distributions(data, features=base_features).savefig('./../dataset/statistics/128_base_features_no_outliers')
        dataset.plot_joint_feature_distributions(data, features=level_features).savefig('./../dataset/statistics/128_level_features_no_outliers')
        dataset.plot_joint_feature_distributions(data, features=floor_features).savefig('./../dataset/statistics/128_floor_features_no_outliers')

    def to_txt(self, json_db, root,  output_path):
        """
        Represent the levels using 2-characters textual information.
        
        
        ENCODING:
        The encoding is in part taken from the TheVGLC dataset, so not all the information is displayed
        Each tile is represented as XY, with X being the VGLC encoding and Y being the ascii-encoding of the trigger tag.
        
        "-" : ["empty","out of bounds"],
        "X" : ["solid","wall"],
        "." : ["floor","walkable"],
        "," : ["floor","walkable","stairs"],
        "E" : ["enemy","walkable"],
        "W" : ["weapon","walkable"],
        "A" : ["ammo","walkable"],
        "H" : ["health","armor","walkable"],
        "B" : ["explosive barrel","walkable"],
        "K" : ["key","walkable"],
        "<" : ["start","walkable"],
        "T" : ["teleport","walkable","destination"],
        ":" : ["decorative","walkable"],
        "L" : ["door","locked"],
        "t" : ["teleport","source","activatable"],
        "+" : ["door","walkable","activatable"],
        ">" : ["exit","activatable"]
        
        :param json_db: 
        :param output_path: 
        :return: 
        """
        import skimage.io as io

        levels = self.read_from_json(json_db)
        for l in levels:
            maps = {}
            for m in Features.map_paths:
                path = l[m]
                map_data = io.imread(root+path)
                maps[Features.map_paths[m]] = map_data

            txtmap = np.ndarray(shape=(2*maps['floormap'].shape[0], maps['floormap'].shape[1]), dtype=np.uint8)
            txtmap[...] = bytearray('-', encoding='ascii')[0]
            txtmap[:, 1::2] = 0
            walls = maps['floormap'] == 255
            pass



DoomDataset().to_txt(json_db='/home/edoardo/Desktop/DoomGAN/DoomDataset Latest/DoomDataset/dataset.json',
                     root='/home/edoardo/Desktop/DoomGAN/DoomDataset Latest/DoomDataset/',
                     output_path='/home/edoardo/Desktop/DoomGAN/DoomDataset Latest/DoomDataset/Processed-txt/')