import ast
import os
import json
import zipfile

from hashlib import md5

# The file that contains json data
PLUGIN_FILE_NAME = "PLUGINS.json"


KNOWN_DATA = [
    'PLUGIN_NAME',
    'PLUGIN_AUTHOR',
    'PLUGIN_VERSION',
    'PLUGIN_API_VERSIONS',
    'PLUGIN_LICENSE',
    'PLUGIN_LICENSE_URL',
    'PLUGIN_DESCRIPTION',
]


def get_plugin_data(filepath):
    """Parse a python file and return a dict with plugin metadata"""
    data = {}
    with open(filepath, 'r') as plugin_file:
        source = plugin_file.read()
        try:
            root = ast.parse(source, filepath)
        except Exception:
            print("Cannot parse " + filepath)
            raise
        for node in ast.iter_child_nodes(root):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if (isinstance(target, ast.Name)
                    and isinstance(target.ctx, ast.Store)
                        and target.id in KNOWN_DATA):
                    name = target.id.replace('PLUGIN_', '', 1).lower()
                    if name not in data:
                        try:
                            data[name] = ast.literal_eval(node.value)
                        except ValueError:
                            print('Cannot evaluate value in '
                                  + filepath + ':' +
                                  ast.dump(node))
        return data


def create_manifest(filepath, manifest_data):
    with open(os.path.join(os.path.dirname(filepath), 'MANIFEST.json')) as f:
        f.write(json.dumps(manifest_data, sort_keys=True, indent=2))


def build_json(source_dir, dest_dir, supported_versions=None):
    """Traverse the plugins directory to generate json data."""

    plugins = {}

    # All top level directories in source_dir are plugins
    for dirname in next(os.walk(source_dir))[1]:

        files = {}
        data = {}

        if dirname in [".git"]:
            continue

        dirpath = os.path.join(source_dir, dirname)
        for root, dirs, filenames in os.walk(dirpath):
            for filename in filenames:
                ext = os.path.splitext(filename)[1]

                if ext not in [".pyc"]:
                    file_path = os.path.join(root, filename)
                    with open(file_path, "rb") as md5file:
                        md5Hash = md5(md5file.read()).hexdigest()
                    files[file_path.split(os.path.join(dirpath, ''))[1]] = md5Hash

                    if ext in ['.py'] and not data:
                        try:
                            data = get_plugin_data(os.path.join(source_dir, dirname, filename))
                        except SyntaxError:
                            print("Unable to parse %s" % filename)
        if files and data:
            print("Added: " + dirname)
            create_manifest(dirname, data)
            data['files'] = files
            plugins[dirname] = data
    out_path = os.path.join(dest_dir, PLUGIN_FILE_NAME)
    with open(out_path, "w") as out_file:
        json.dump({"plugins": plugins}, out_file, sort_keys=True, indent=2)


def get_valid_plugins(dest_dir):
    plugin_file = os.path.join(dest_dir, PLUGIN_FILE_NAME)
    if os.path.exists(plugin_file):
        with open(os.path.join(dest_dir, PLUGIN_FILE_NAME)) as f:
            plugin_data = json.loads(f.read())
            return list(plugin_data['plugins'].keys())


def package_files(source_dir, dest_dir):
    """Zip up plugin folders"""
    valid_plugins = get_valid_plugins(dest_dir)

    for dirname in next(os.walk(source_dir))[1]:
        if ((valid_plugins and dirname in valid_plugins)
            or not valid_plugins):
            archive_path = os.path.join(dest_dir, dirname) + ".picard.zip"
            archive = zipfile.ZipFile(archive_path, "w")

            dirpath = os.path.join(source_dir, dirname)
            plugin_files = []

            for root, dirs, filenames in os.walk(dirpath):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    plugin_files.append(file_path)

            if len(plugin_files) == 1:
                # There's only one file, put it directly into the zipfile
                archive.write(plugin_files[0],
                              os.path.basename(plugin_files[0]),
                              compress_type=zipfile.ZIP_DEFLATED)
            else:
                for filename in plugin_files:
                    # Preserve the folder structure relative to source_dir
                    # in the zip file
                    name_in_zip = os.path.join(os.path.relpath(filename,
                                                               source_dir))
                    archive.write(filename,
                                  name_in_zip,
                                  compress_type=zipfile.ZIP_DEFLATED)
            with open(archive_path, "rb") as source, open(archive_path + ".md5", "w") as md5file:
                md5file.write(md5(source.read()).hexdigest())
            print("Created: " + archive_path)


def validate_plugin(archive_path):
    with open(archive_path, "rb") as source, open(archive_path + ".md5") as md5file:
        if md5file.read() == md5(source.read()).hexdigest():
            return True
    return False