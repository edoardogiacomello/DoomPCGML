import matplotlib.pyplot as plt
import numpy as np
import seaborn as sb
import DoomLevelsGAN.DoomGAN as nn
from WAD_Parser.Dictionaries import Features as all_features
import os
import json


def generate_results_and_save(samples_per_map):
    """
    Loads the network and generates <samples_for_map> features for every map in the training set.
    Results are saved into the artifacts folder.
    :param samples_per_map: How many samples to generate for each "true" map.
    :return:
    """
    if samples_per_map == 1:

        names, true_features, oth_true_features, generated_features, oth_gen_features, noise = nn.gan.evaluate_samples_distribution(n=samples_per_map)
        np.save(nn.FLAGS.ref_sample_folder+'results_names.npy', names)
        np.save(nn.FLAGS.ref_sample_folder+'results_true.npy', true_features)
        np.save(nn.FLAGS.ref_sample_folder+'results_true_oth.npy', oth_true_features)
        np.save(nn.FLAGS.ref_sample_folder+'results_gen.npy', generated_features)
        np.save(nn.FLAGS.ref_sample_folder+'results_gen_oth.npy', oth_gen_features)
        np.save(nn.FLAGS.ref_sample_folder+'results_noise.npy', noise)
    else:
        percent_dict = load_level_subset()
        true_samples = dict()
        for p in percent_dict:
            for name in percent_dict[p]:
                true_samples[name] = None
        true_samples = nn.gan.get_samples_by_name(true_samples)
        while None in true_samples.values():
            print(
                "Not all levels have been found, due to random selection of levels to match the batch size. Retrying..")
            true_samples = nn.gan.get_samples_by_name(true_samples)
        names, generated = nn.gan.evaluate_samples_distribution(input_subset=true_samples, n=samples_per_map)
        path = nn.FLAGS.ref_sample_folder + 'samples_percentiles/generated1v{}'.format(samples_per_map)
        np.save(path + 'names.npy', names)
        np.save(path + 'generated.npy', generated)


def load_results_from_files():
    """Loads previously saved results from the artifacts folder"""
    names = np.load(nn.FLAGS.ref_sample_folder + 'results_names.npy')
    true_features = np.load(nn.FLAGS.ref_sample_folder + 'results_true.npy').astype(np.float32)
    oth_true_features = np.load(nn.FLAGS.ref_sample_folder + 'results_true_oth.npy').astype(np.float32)
    generated_features = np.load(nn.FLAGS.ref_sample_folder + 'results_gen.npy').astype(np.float32)
    oth_gen_features = np.load(nn.FLAGS.ref_sample_folder + 'results_gen_oth.npy').astype(np.float32)
    noise = np.load(nn.FLAGS.ref_sample_folder + 'results_noise.npy').astype(np.float32)
    return names, true_features, oth_true_features, generated_features, oth_gen_features, noise


def clean_nans(a):
    """
    Removes rows from a that contains non numerical values
    :param a:
    :return:
    """
    if len(a.shape) == 1:
        return a[~np.isnan(a)]
    return a[~np.isnan(a).any(axis=1)]

def distribution_visualization_1v1(colors={'True':'red', 'Gen':'dodgerblue'}):
    """
    Plots true vs generated distribution (1 generated vector for each true one) for each feature that is possible to extract from generated samples (both in input to the network or not)
    Requires data file 'results_*.npy' to be in the artifacts folder.
    Saves the image results in the artifact folder
    :param colors:
    :return:
    """
    features_output_folder = nn.FLAGS.ref_sample_folder + "graphs/1v1/input_features/"
    oth_features_output_folder = nn.FLAGS.ref_sample_folder + "graphs/1v1/other_features/"

    os.makedirs(features_output_folder+"png/",exist_ok=True)
    os.makedirs(features_output_folder+"pdf/",exist_ok=True)
    os.makedirs(oth_features_output_folder+"png/",exist_ok=True)
    os.makedirs(oth_features_output_folder+"pdf/",exist_ok=True)

    oth_features = [f for f in all_features.features_for_evaluation if f not in nn.gan.features]

    names, true, oth_true, gen, oth_gen, noise = load_results_from_files()
    # fixing the first dimension
    gen = np.squeeze(gen,-1) if len(nn.gan.features) > 0 else gen
    oth_gen = np.squeeze(oth_gen,-1)

    # Showing True features distribution vs Generated for the input features
    for f, fname in enumerate(nn.features):
        # Clearing rows containing NaNs, from now on the correspondence between indices/level name is lost

        tc = clean_nans(true[:,f])
        gc = clean_nans(gen[:,f])

        fig = plt.figure()
        axt = sb.rugplot([tc.mean()], height=1, ls="--", color=colors['True'], linewidth=0.75)
        sb.kdeplot(tc, ax=axt, label="True",ls="--", color=colors['True'])

        axg = sb.rugplot([gc.mean()], height=1, color=colors['Gen'], linewidth=0.75)
        sb.kdeplot(gc, ax=axg, label="Generated", color=colors['Gen'])

        axt.set_xlabel("{}".format(fname))
        fig_name = "1v1_{}".format(fname)
        axt.figure.canvas.set_window_title(fig_name)

        fig.savefig(features_output_folder+'png/'+fig_name+'.png')
        fig.savefig(features_output_folder+'pdf/'+fig_name+'.pdf')
        plt.close(fig)

    for f, fname in enumerate(oth_features):
        otc = clean_nans(oth_true[:, f])
        ogc = clean_nans(oth_gen[:, f])
        fig = plt.figure()
        axt = sb.rugplot([otc.mean()], height=1, ls="--", color=colors['True'], linewidth=0.75)
        sb.kdeplot(otc, ax=axt, label="True", ls="--",  color=colors['True']) if np.unique(otc, axis=0).size > 1 else None
        # Don't show the distribution if data contains only a value -> matrix is singular


        axg = sb.rugplot([ogc.mean()], height=1, color=colors['Gen'], linewidth=0.75)
        sb.kdeplot(ogc, ax=axg, label="Generated",  color=colors['Gen']) if np.unique(ogc, axis=0).size > 1 else None
        # Don't show the distribution if data contains only a value -> matrix is singular

        axt.set_xlabel("{}".format(fname))
        fig_name = "1v1_{}".format(fname)
        axt.figure.canvas.set_window_title(fig_name)
        axt.figure.savefig(oth_features_output_folder+'png/'+fig_name+'.png')
        axt.figure.savefig(oth_features_output_folder+'pdf/'+fig_name+'.pdf')
        plt.close(fig)


def pick_samples_from_feature_percentiles():
    """
    Composes a set of samples picking the 0,25,50,75 and 100th percentile from the distribution of each input feature.
    Result is saved into the artifacts folder
    """
    samples_output_folder = nn.FLAGS.ref_sample_folder + 'samples_percentiles/'
    os.makedirs(samples_output_folder, exist_ok=True)

    percent_dict = dict() # Sample names organized by percentiles
    names, true, oth_true, gen, oth_gen, noise = load_results_from_files()
    percentiles = [0,25,50,75,100];
    feat_list_perc = list() # List containing feature values corresponding to the percentiles (perc, features)
    for perc in percentiles:
        pr = np.nanpercentile(true, perc, axis=0)
        indices = np.abs(true - pr).argmin(axis=0)
        feat_list_perc.append(np.diag(true[indices]))
        percent_dict['perc{}'.format(perc)] = names[indices]

    # Building a dictionary for associating name and real sample
    samples = dict()
    for p in percent_dict:
        for n in percent_dict[p]:
            samples[n] = None
    samples = nn.gan.get_samples_by_name(samples)
    while None in samples.values():
        print("Not all levels have been found, due to random selection of levels to match the batch size. Retrying..")
        samples = nn.gan.get_samples_by_name(samples)

    for f, fname in enumerate(nn.gan.features):
        fig = plt.figure()
        plt.subplot()
        for p, pname in enumerate(percent_dict):
            name = percent_dict[pname][f]
            ax = plt.subplot(3, len(percent_dict), p+1)
            ax.set_xticks([])
            ax.set_yticks([])
            plt.imshow(samples[name]['floormap'][0])
            plt.title("{}".format(pname))
        for p, pname in enumerate(percent_dict):
            name = percent_dict[pname][f]
            ax = plt.subplot(3, len(percent_dict), len(percent_dict) + p+1)
            ax.set_xticks([])
            ax.set_yticks([])
            plt.imshow(samples[name]['roommap'][0])
            plt.title("{}".format(pname))
        # Distribution plot
        dax = plt.subplot(3,1,3)
        values = [samples[percent_dict[p][f]][fname][0] for p in percent_dict]
        x = range(1, len(values)+1)
        plt.plot(x, values, 'o')
        dax.set_xticks(x)
        plt.title("{}".format("{}_distribution".format(fname)))
        fig.canvas.set_window_title('samples_{}'.format(fname))

        # Saving the feature vector
        fig.savefig(samples_output_folder+'samples_{}.png'.format(fname))
        fig.savefig(samples_output_folder+'samples_{}.pdf'.format(fname))
    with open(samples_output_folder + 'samples_names.json', 'w') as jout:
        # Converting percent_dict from ndarray of np.bytes to list of strings
        converted = {k: [n.decode('utf-8') for n in percent_dict[k].tolist()] for k in percent_dict}
        json.dump(converted, jout)

def load_level_subset():
    """ Loads the json file containing the list of level names for the 1vsN comparison"""
    samples_output_folder = nn.FLAGS.ref_sample_folder + 'samples_percentiles/'
    with open(samples_output_folder + 'samples_names.json', 'r') as jin:
        percent_dict = json.load(jin)
    return percent_dict

def distribution_visualization_1vN(n, load=False, colors=['r','g','b','c','gray', 'm']):
    """ Plots a graph for each input feature, showing the generated sample distribution around the true feature for
    the samples that are positioned at the (0, 25, 50, 75, 100)th percentiles. """
    output_graph_folder = nn.FLAGS.ref_sample_folder + "graphs/1v{}/input_features/".format(n)
    os.makedirs(output_graph_folder, exist_ok=True)
    percent_dict = load_level_subset()
    true_samples = dict()
    for p in percent_dict:
        for name in percent_dict[p]:
            true_samples[name] = None
    true_samples = nn.gan.get_samples_by_name(true_samples)
    while None in true_samples.values():
        print("Not all levels have been found, due to random selection of levels to match the batch size. Retrying..")
        true_samples = nn.gan.get_samples_by_name(true_samples)

    # loading generated results
    path = nn.FLAGS.ref_sample_folder + 'samples_percentiles/generated1v{}'.format(n)
    names = np.load(path+'names.npy'.format(n))
    generated = np.load(path+'generated.npy'.format(n))

    gen_samples = dict()
    for n_id, name in enumerate(names):
        gen_samples[name] = generated[n_id,...]

    # Input features, only relevant levels
    for f, fname in enumerate(nn.gan.features):
        fig = plt.figure(figsize=(15,11))
        for p, pname in enumerate(percent_dict):
            name = percent_dict[pname][f]
            samp = generated[np.where(names == name)][0]
            true_value = true_samples[name][fname]
            values = samp[fname]
            #axt = sb.rugplot([np.mean(values)], height=1, ls="-", linewidth=0.75, color=colors[p])
            axt = sb.rugplot(true_value, height=1, ls="--", linewidth=0.75, label="True", color=colors[p])
            sb.kdeplot(values, ax=axt, ls="-", label="Generated_{}".format(pname), color=colors[p])

        plt.title("{}".format("{}".format(fname)))
        fig.canvas.set_window_title("{}".format("{}".format(fname)))
        fig.savefig(output_graph_folder + '1v{}_{}.png'.format(n, fname))
        fig.savefig(output_graph_folder + '1v{}_{}.pdf'.format(n, fname))
