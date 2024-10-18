import json
from typing import List, TypedDict
from typing_extensions import assert_never
from unittest.mock import patch

import pytest
from flask.json import jsonify
from flask.wrappers import Response

from flask_ml.flask_ml_client import MLClient
from flask_ml.flask_ml_server import MLServer
from flask_ml.flask_ml_server.models import *

from .constants import *


class MockResponse:
    def __init__(self, response: Response):
        self.status_code = response.status_code
        self.headers = {"Content-Type": "application/json"}
        self.response: Response = response

    def json(self):
        return self.response.get_json()


def create_response_model(results: BaseModel):
    return Response(response=results.model_dump_json(), status=200, mimetype="application/json")


def mock_post_request(url, json=None, **kwargs) -> MockResponse:
    data = RequestBody.model_validate(json)
    if url == "http://127.0.0.1:5000/process_text":
        return MockResponse(create_response_model(process_text(data.inputs["text_inputs"].root.texts, data.parameters)))  # type: ignore
    elif url == "http://127.0.0.1:5000/process_file":
        return MockResponse(create_response_model(process_file(data.inputs["file_inputs"].root.files, data.parameters)))  # type: ignore
    assert False, "Never"


def process_text(inputs: List[TextInput], parameters):
    results = [TextResponse(title=inp.text, value="processed_text.txt") for inp in inputs]
    results = BatchTextResponse(texts=results)
    return results


def process_file(inputs: List[FileInput], parameters):
    results = [
        FileResponse(title=inp.path, path="processed_image.img", file_type=FileType.IMG) for inp in inputs
    ]
    results = BatchFileResponse(files=results)
    return results


@pytest.fixture
def app():
    server = MLServer(__name__)

    class TextInputs(TypedDict):
        text_inputs: BatchTextInput

    class Parameters(TypedDict):
        pass

    class FileInputs(TypedDict):
        file_inputs: BatchFileInput

    @server.route("/process_text")
    def server_process_text(inputs: TextInputs, parameters: Parameters) -> ResponseBody:
        return ResponseBody(root=process_text(inputs["text_inputs"].texts, parameters))

    @server.route("/process_file")
    def server_process_image(inputs: FileInputs, parameters: Parameters) -> ResponseBody:
        return ResponseBody(root=process_file(inputs["file_inputs"].files, parameters))

    def task_schema_func() -> TaskSchema:
        return TaskSchema(
            inputs=[InputSchema(key="file_inputs", label="File Inputs", input_type=InputType.BATCHFILE)],
            parameters=[
                ParameterSchema(
                    key="param1",
                    label="Parameter 1",
                    value=RangedFloatParameterDescriptor(
                        parameter_type=ParameterType.RANGED_FLOAT,
                        range=FloatRangeDescriptor(min=0, max=1),
                        default=0.5,
                    ),
                )
            ],
        )

    class ParametersWithSchema(TypedDict):
        param1: float

    @server.route("/process_file_with_schema", task_schema_func)
    def server_process_image_with_schema(
        inputs: FileInputs, parameters: ParametersWithSchema
    ) -> ResponseBody:
        return ResponseBody(root=process_file(inputs["file_inputs"].files, parameters))

    return server.app.test_client()


@pytest.fixture
def client():
    return MLClient("http://127.0.0.1:5000/predict")


def test_list_routes(app):
    response = app.get("/api/routes")
    assert response.status_code == 200
    assert response.json == [
        {
            "payload_schema": "/process_text/payload_schema",
            "run_task": "/process_text",
            "sample_payload": "/process_text/sample_payload",
        },
        {
            "payload_schema": "/process_file/payload_schema",
            "run_task": "/process_file",
            "sample_payload": "/process_file/sample_payload",
        },
        {
            "order": 0,
            "payload_schema": "/process_file_with_schema/payload_schema",
            "run_task": "/process_file_with_schema",
            "sample_payload": "/process_file_with_schema/sample_payload",
            "short_title": "",
            "task_schema": "/process_file_with_schema/task_schema",
        },
    ]


def test_empty_list_routes():
    server = MLServer(__name__)
    app = server.app.test_client()
    response = app.get("/api/routes")
    assert response.status_code == 200
    assert response.json == []


def test_payload_schema(app):
    response = app.get("/process_file/payload_schema")
    assert response.status_code == 200
    assert "$defs" in response.json


def test_sample_payload(app):
    response = app.get("/process_file/sample_payload")
    assert response.status_code == 200
    assert response.json == {
        "inputs": {
            "file_inputs": {"files": [{"path": "/Users/path/to/file1"}, {"path": "/Users/path/to/file2"}]}
        },
        "parameters": {},
    }


def test_payload_schema_with_task_schema(app):
    response = app.get("/process_file_with_schema/payload_schema")
    assert response.status_code == 200
    assert "$defs" in response.json


def test_sample_payload_with_task_schema(app):
    response = app.get("/process_file_with_schema/sample_payload")
    assert response.status_code == 200
    assert response.json == {
        "inputs": {
            "file_inputs": {"files": [{"path": "/Users/path/to/file1"}, {"path": "/Users/path/to/file2"}]}
        },
        "parameters": {"param1": 0.0},
    }


def test_task_schema(app):
    response = app.get("process_file_with_schema/task_schema")
    assert response.status_code == 200
    assert response.json == {
        "inputs": [{"input_type": "batchfile", "key": "file_inputs", "label": "File Inputs", "subtitle": ""}],
        "parameters": [
            {
                "key": "param1",
                "label": "Parameter 1",
                "subtitle": "",
                "value": {
                    "default": 0.5,
                    "parameter_type": "ranged_float",
                    "range": {"max": 1.0, "min": 0.0},
                },
            }
        ],
    }


def test_valid_file_request_for_endpoint_with_task_schema(app):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {"param1": 0.0},
    }

    response = app.post("/process_file_with_schema", json=data)
    assert response.status_code == 200
    assert response.json == {
        "output_type": "batchfile",
        "files": [
            {
                "output_type": "file",
                "file_type": "img",
                "path": "processed_image.img",
                "title": "/path/to/image.jpg",
                "subtitle": None,
            }
        ],
    }

def test_bad_request_input_validation_error_for_endpoint_with_schema(app):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {"INCORRECT KEY": 0.0},
    }

    response = app.post("/process_file_with_schema", json=data)
    assert response.status_code == 400
    assert "Keys mismatch." in response.json['error']

def test_bad_request_param_validation_error_for_endpoint_with_schema(app):
    data = {
        "inputs": {"INCORRECT_KEY": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {"param1": 0.0},
    }

    response = app.post("/process_file_with_schema", json=data)
    assert response.status_code == 400
    assert "Keys mismatch." in response.json['error']

def test_invalid_request_param_validation_error_for_endpoint_with_schema(app):
    data = {
        "inputs": {"file_inputs": {"incorret_key": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {"param1": 0.0},
    }

    response = app.post("/process_file_with_schema", json=data)
    assert response.status_code == 400
    assert "Field required" in response.json['error'][0]['msg']


def test_set_url(client):
    new_url = "http://localhost:8000/sentimentanalysis"
    client.set_url(new_url)
    assert client.url == new_url


def test_valid_text_request(app):
    data = {
        "inputs": {"text_inputs": {"texts": [{"text": "Sample text"}]}},
        "parameters": {},
    }

    response = app.post("/process_text", json=data)
    assert response.status_code == 200
    assert response.json == {
        "output_type": "batchtext",
        "texts": [
            {"output_type": "text", "value": "processed_text.txt", "title": "Sample text", "subtitle": None}
        ],
    }


@patch("requests.post")
def test_valid_text_request_client(mock_post, client: MLClient):
    data = {
        "inputs": {"text_inputs": {"texts": [{"text": "Sample text"}]}},
        "parameters": {},
    }

    mock_post.return_value = mock_post_request("http://127.0.0.1:5000/process_text", json=data)
    response = client.request(data["inputs"], data["parameters"])
    assert response == {
        "output_type": "batchtext",
        "texts": [
            {"output_type": "text", "value": "processed_text.txt", "title": "Sample text", "subtitle": None}
        ],
    }


def test_invalid_text_request(app):
    data = {
        "inputs": {"KEY_INVALID": {"texts": [{"text": "Sample text"}]}},
        "parameters": {},
    }
    response = app.post("/process_text", json=data)
    assert response.status_code == 400
    assert "VALIDATION_ERROR" == response.json["status"]
    assert "Keys mismatch. The input schema has" in response.json["error"]


def test_valid_file_request(app):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {},
    }

    response = app.post("/process_file", json=data)
    assert response.status_code == 200
    assert response.json == {
        "output_type": "batchfile",
        "files": [
            {
                "output_type": "file",
                "file_type": "img",
                "path": "processed_image.img",
                "title": "/path/to/image.jpg",
                "subtitle": None,
            }
        ],
    }


@patch("requests.post")
def test_valid_file_request_client(mock_post, client):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {},
    }

    mock_post.return_value = mock_post_request("http://127.0.0.1:5000/process_file", json=data)
    response = client.request(data["inputs"], data["parameters"])

    assert response == {
        "output_type": "batchfile",
        "files": [
            {
                "output_type": "file",
                "file_type": "img",
                "path": "processed_image.img",
                "title": "/path/to/image.jpg",
                "subtitle": None,
            }
        ],
    }


@patch("requests.post")
def test_invalid_reponse_not_json(mock_post, client):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {},
    }
    mock_post.return_value = mock_post_request("http://127.0.0.1:5000/process_file", json=data)
    mock_post.return_value.headers = {"Content-Type": "text/html"}
    response = client.request(data["inputs"], data["parameters"])
    assert "Unknown error" in response["status"]
    assert "errors" in response
    assert "Unknown error" in response["errors"][0]["msg"]


@patch("requests.post")
def test_non_200_reponse(mock_post, client):
    data = {
        "inputs": {"file_inputs": {"files": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {},
    }
    mock_post.return_value = MockResponse(
        response=Response(response=json.dumps({"status": "failed"}), status=400, mimetype="application/json")
    )
    mock_post.return_value.status_code = 400
    response = client.request(data["inputs"], data["parameters"])
    assert {"status": "failed"} == response


def test_invalid_file_request(app):
    data = {
        "inputs": {"file_inputs": {"INVALID_KEY": [{"path": "/path/to/image.jpg"}]}},
        "parameters": {},
    }
    response = app.post("/process_file", json=data)

    assert response.status_code == 400
    assert "VALIDATION_ERROR" == response.json["status"]
    assert "Field required" == response.json["error"][0]["msg"]
