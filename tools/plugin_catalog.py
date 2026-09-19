"""Small, explicit console library. Names bind to live Ardour descriptors.

Never enumerate the workstation's VST/LV2 inventory here. The native endpoint
has the same allowlisted keys and chooses mono/stereo at insertion time.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
CATALOG = (
    ('eq', 'LSP EQ8', ('LSP Parametric Equalizer x8 Mono', 'LSP Parametric Equalizer x8 Stereo')),
    ('comp', 'LSP Comp', ('LSP Compressor Mono', 'LSP Compressor Stereo')),
    ('reverb', 'Reverb', ('Dragonfly Room Reverb',)),
    ('delay', 'Delay', ('ZamDelay',)),
    ('phaser', 'Phaser', ('LFO Phaser',)),
    ('warm', 'Chaleur', ('Valve saturation',)),
    ('tube', 'Tube', ('ZamTube',)),
    ('tape', 'Tape', ('CHOWTapeModel',)),
)

# label, console caption, unit, per-detent increment (None = descriptor rule).
PROFILES = {
    'warm': (
        ('Distortion level', 'Chaleur', '%01', .01),
        ('Distortion character', 'Caract.', '%01', .01),
    ),
    'tube': (
        ('Tube Drive', 'Drive', '', .1), ('Input level', 'Niveau', 'dB', .25),
        ('Bass', 'Graves', '', .1), ('Mids', 'Mediums', '', .1),
        ('Treble', 'Aigus', '', .1), ('Tone Stack Model', 'Modele', '', None),
        ('Insane Boost', 'Boost', '', None),
    ),
    # CHOW's LV2 wrapper exports normalized 0..1 parameters. Wow/flutter
    # rates also use this scale in its own GUI: do not mislabel them as Hz.
    'tape': (
        ('Wow Depth', 'WowProf', '%01', .01), ('Wow Rate', 'WowVit', '%01', .01),
        ('Flutter Depth', 'FlutProf', '%01', .01), ('Flutter Rate', 'FlutVit', '%01', .01),
        ('Tape Drive', 'Drive', '%01', .01), ('Tape Saturation', 'Satur.', '%01', .01),
        ('Dry/Wet', 'Melange', '%01', .01), ('Output Gain', 'Sortie', 'tape_out_db', 1/240),
        ('Wow Variance', 'Alea', '%01', .01), ('Wow Drift', 'Derive', '%01', .01),
        ('Tape Bias', 'Bias', '%01', .01), ('Input Gain', 'Entree', 'tape_in_db', 1/144),
        ('Tape On/Off', 'Bande', 'bool', 1), ('Wow/Flutter On/Off', 'Detune', 'bool', 1),
    ),
    'reverb': (
        ('Decay', 'Duree', 's', .05), ('Predelay', 'Predelay', 'ms', 1),
        ('Size', 'Taille', 'm', .5), ('Late Level', 'Reverb', '%', 1),
        ('Early Level', 'Reflets', '%', 1), ('Dry Level', 'Direct', '%', 1),
        ('High Cut', 'CoupeHt', 'Hz', 100), ('Width', 'Largeur', '%', 1),
        ('Early Send', 'EnvoiRef', '%', 1), ('Diffuse', 'Diffus', '%', 1),
        ('Spin', 'ModVit', 'Hz', .05), ('Wander', 'ModProf', '%', 1),
        ('Early Damp', 'AmortRef', 'Hz', 100), ('Late Damp', 'AmortRev', 'Hz', 100),
        ('Low Boost', 'Graves', '%', 1), ('Boost Freq', 'FreqGrav', 'Hz', 10),
        ('Low Cut', 'CoupeBas', 'Hz', 1),
    ),
    'delay': (
        ('Time', 'Temps', 'ms', 5), ('Feedback', 'Retour', '%01', .01),
        ('Dry/Wet', 'Melange', '%01', .01), ('LPF', 'CoupeHt', 'Hz', 100),
        ('Sync BPM', 'SyncBPM', '', None), ('Divisor', 'Division', '', None),
        ('Output Gain', 'Sortie', 'dB', .25), ('Invert', 'Inverse', '', None),
    ),
    'phaser': (
        ('LFO rate (Hz)', 'Vitesse', 'Hz', .05), ('LFO depth', 'Profond', '%01', .01),
        ('Feedback', 'Retour', '%01', .01), ('Spread (octaves)', 'Etendue', 'oct', .05),
    ),
}


def minimum_version(key):
    return 2 if key in ('warm', 'tube', 'tape') else 1


def entry_for_name(name):
    return next((entry for entry in CATALOG if name in entry[2]), None)


def profile_for_name(name):
    entry = entry_for_name(name)
    return PROFILES.get(entry[0], ()) if entry else ()
