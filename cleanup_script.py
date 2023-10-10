import os
import requests
from getpass import getpass
from dateutil.parser import parse

repository_url = os.environ.get("NXRM_REPOSITORY_URL", "https://repository.dev.dynabic.com")
num_tags_to_keep = int(os.environ.get("NXRM_NUM_TAGS_TO_KEEP", 10))

nxrm_username = os.environ.get("NXRM_USERNAME")
nxrm_password = os.environ.get("NXRM_PASSWORD")
nxrm_except_registries = os.environ.get("NXRM_EXCEPT_REGISTRIES", "")
nxrm_images_to_exclude = os.environ.get("NXRM_IMAGES_TO_EXCLUDE", "")

if not nxrm_username or not nxrm_password:
    print("Please set NXRM_USERNAME and NXRM_PASSWORD environment variables")
    exit()

except_registries = [repo.strip() for repo in nxrm_except_registries.split(",") if repo.strip()]
images_to_exclude = [x.strip() for x in nxrm_images_to_exclude.split(",") if x.strip()]

repositories_url = f"{repository_url}/service/rest/v1/repositories"
response = requests.get(repositories_url, auth=(nxrm_username, nxrm_password))
response.raise_for_status()
repositories = response.json()

for repository in repositories:
    if repository["format"] != "docker":
        continue

    repository_name = repository["name"]

    if repository_name in except_registries:
        print(f"Skipping excluded repository {repository_name}...")
        continue

    print(f"Processing repository {repository_name}...")

    images_url = f"{repository_url}/repository/{repository_name}/v2/_catalog"
    response = requests.get(images_url, auth=(nxrm_username, nxrm_password))
    images = response.json()["repositories"]

    for image_name in images:
        if image_name in images_to_exclude:
            print(f"Skipping excluded image {image_name} in repository {repository_name}...")
            continue

        print(f"Processing image {image_name} in repository {repository_name}...")

        tags_url = f"{repository_url}/repository/{repository_name}/v2/{image_name}/tags/list"
        response = requests.get(tags_url, auth=(nxrm_username, nxrm_password))
        tags = response.json()["tags"]

        tags_with_created_date = []
        for tag_name in tags:
            manifest_headers = {
                "Accept": "application/vnd.docker.distribution.manifest.v2+json"
            }
            manifest_url = f"{repository_url}/repository/{repository_name}/v2/{image_name}/manifests/{tag_name}"
            manifest_response = requests.get(manifest_url, auth=(nxrm_username, nxrm_password), headers=manifest_headers)
            manifest_digest = manifest_response.json()["config"]["digest"]

            digest_url = f"{repository_url}/repository/{repository_name}/v2/{image_name}/blobs/{manifest_digest}"
            digest_response = requests.get(digest_url, auth=(nxrm_username, nxrm_password), headers=manifest_headers)
            created_date = parse(digest_response.json()["created"])
            tags_with_created_date.append((tag_name, created_date))

            print(f"Found tag {tag_name} with created date {created_date}")

        tags_with_created_date.sort(key=lambda x: x[1], reverse=True)

        tags_to_delete = [tag[0] for tag in tags_with_created_date[num_tags_to_keep:]]

        for tag_name in tags_to_delete:
            print(f"Deleting tag {tag_name} in image {image_name} in repository {repository_name}...")
            manifest_url = f"{repository_url}/repository/{repository_name}/v2/{image_name}/manifests/{tag_name}"
            manifest_response = requests.get(manifest_url, auth=(nxrm_username, nxrm_password), headers=manifest_headers)
            manifest_digest = manifest_response.headers.get("Docker-Content-Digest")
            if manifest_digest is not None:
                delete_url = f"{repository_url}/repository/{repository_name}/v2/{image_name}/manifests/{manifest_digest}"
                delete_response = requests.delete(delete_url, auth=(nxrm_username, nxrm_password), headers=manifest_headers)

                if delete_response.status_code == 202:
                    print(f"Deleted tag {tag_name} in image {image_name} in repository {repository_name}")
                else:
                    print(f"Failed to delete tag {tag_name} in image {image_name} in repository {repository_name}. Status code: {delete_response.status_code}")
            else:
                print(f"Failed to retrieve manifest digest for tag {tag_name} in image {image_name} in repository {repository_name}")
