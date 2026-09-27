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
    ('autotune', 'Autotune', ('x42-Autotune',)),
    ('pitch', 'Harmonie', ('Rubber Band Mono Pitch Shifter', 'Rubber Band Stereo Pitch Shifter')),
    ('sidechain', 'Sidechain', ('LSP Sidechain Compressor Mono', 'LSP Sidechain Compressor Stereo')),
    ('pump', 'Pump LFO', ('B.Shapr',)),
    ('transient', 'Attaques', ('LSP Beat Breather Mono', 'LSP Beat Breather Stereo')),
    ('vocoder', 'Vocodeur', ('Surge XT Effects',)),
)

# label, console caption, unit, per-detent increment (None = descriptor rule).
PROFILES = {
    'autotune': (
        ('Correction', 'Quantite', '%01', .01), ('Filter', 'Suivi', 's', .005),
        ('Bias', 'Biais', '%01', .01), ('Offset', 'Decalage', 'st', .05),
        ('Tuning', 'Accord', 'Hz', .1), ('Mode', 'Mode', '', None),
        ('Fast Correction', 'Rapide', 'bool', 1), ('Pitch Bend Range', 'Bend', 'st', None),
    ),
    'pitch': (
        ('Semitones', 'Interval', 'st', 1), ('Cents', 'Fin', 'ct', 1),
        ('Octaves', 'Octave', 'oct', 1), ('Wet-Dry Mix', 'Direct', '%01', .01),
        ('Formant Preserving', 'Formants', 'bool', 1), ('Crispness', 'Texture', '', None),
    ),
    'sidechain': (
        ('Attack threshold', 'Seuil', 'gain_db', .25), ('Ratio', 'Ratio', ':1', .1),
        ('Attack time', 'Attaque', 'ms', .1), ('Release time', 'Relache', 'ms', 1),
        ('Knee', 'Coude', 'gain_db', .25), ('Makeup gain', 'Compens', 'gain_db', .25),
        ('Wet gain', 'Traite', 'gain_db', .25), ('Output gain', 'Sortie', 'gain_db', .25),
    ),
    'pump': (
        ('Dry / wet', 'Melange', '%01', .01), ('Base value', 'Duree', '', 1),
        ('Base', 'Unite', '', None), ('Shaper 1: smoothing', 'Lissage', 'ms', 1),
        ('Shaper 1: dry / wet', 'Profonde', '%01', .01),
        ('Shaper 1: output amplification', 'Sortie', 'gain_db', .25),
    ),
    'transient': (
        ('Beat processor attack time 1', 'Attaque', 'ms', .1),
        ('Beat processor release time 1', 'Relache', 'ms', 1),
        ('Beat processor expand ratio 1', 'Ratio', ':1', .1),
        ('Beat processor maximum gain 1', 'MaxGain', 'gain_db', .25),
        ('Punch filter threshold 1', 'Seuil', 'gain_db', .25),
        ('Band output gain 1', 'Bande1', 'gain_db', .25),
        ('Dry gain', 'Direct', 'gain_db', .25), ('Wet gain', 'Traite', 'gain_db', .25),
    ),
    # Descriptor names change with Surge's effect type. Requiring these names
    # gates this profile to the vocoder; normalized values stay percentages.
    'vocoder': (
        ('Input Gain', 'Entree', '%01', .01), ('Input Gate', 'Gate', '%01', .01),
        ('Filter Bank Env Follow', 'Suivi', '%01', .01), ('Filter Bank Q', 'Q', '%01', .01),
        ('Carrier Bands', 'Bandes', '%01', .01), ('Carrier Min Frequency', 'Bas', '%01', .01),
        ('Carrier Max Frequency', 'Haut', '%01', .01), ('Output Mix', 'Melange', '%01', .01),
        ('Modulator Input', 'ModIn', '%01', .01), ('Modulator Range', 'Etendue', '%01', .01),
        ('Modulator Center', 'Centre', '%01', .01),
    ),
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
    if key in ('autotune', 'pitch', 'sidechain', 'pump', 'transient', 'vocoder'): return 3
    return 2 if key in ('warm', 'tube', 'tape') else 1


def entry_for_name(name):
    return next((entry for entry in CATALOG if name in entry[2]), None)


def profile_for_name(name):
    entry = entry_for_name(name)
    return PROFILES.get(entry[0], ()) if entry else ()
