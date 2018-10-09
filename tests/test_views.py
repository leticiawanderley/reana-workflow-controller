# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2017, 2018 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""REANA-Workflow-Controller module tests."""

import io
import json
import os
import uuid

import fs
import mock
import pytest
from flask import url_for
from pytest_reana.fixtures import (cwl_workflow_with_name,
                                   cwl_workflow_without_name, default_user,
                                   session, tmp_shared_volume_path,
                                   yadage_workflow_with_name)
from reana_db.models import Workflow, WorkflowStatus
from werkzeug.utils import secure_filename

from reana_workflow_controller.rest import START, STOP

status_dict = {
    START: WorkflowStatus.running,
    STOP: WorkflowStatus.finished
}


def test_get_workflows(app, session, default_user, cwl_workflow_with_name):
    """Test listing all workflows."""
    with app.test_client() as client:
        workflow_uuid = uuid.uuid4()
        workflow_name = 'my_test_workflow'
        workflow = Workflow(
            id_=workflow_uuid,
            name=workflow_name,
            status=WorkflowStatus.finished,
            owner_id=default_user.id_,
            reana_specification=cwl_workflow_with_name['reana_specification'],
            type_=cwl_workflow_with_name[
                'reana_specification']['type'],
            logs='')
        session.add(workflow)
        session.commit()
        res = client.get(url_for('api.get_workflows'),
                         query_string={"user": default_user.id_})
        assert res.status_code == 200
        response_data = json.loads(res.get_data(as_text=True))
        expected_data = [
            {
                "id": str(workflow.id_),
                "name": workflow.name + '.1',  # Add run_number
                "status": workflow.status.name,
                "user": str(workflow.owner_id),
                "created": response_data[0]["created"]
            }
        ]

        assert response_data == expected_data


def test_get_workflows_wrong_user(app):
    """Test list of workflows for unknown user."""
    with app.test_client() as client:
        random_user_uuid = uuid.uuid4()
        res = client.get(url_for('api.get_workflows'),
                         query_string={"user": random_user_uuid})
        assert res.status_code == 404


def test_get_workflows_missing_user(app):
    """Test listing all workflows with missing user."""
    with app.test_client() as client:
        res = client.get(url_for('api.get_workflows'),
                         query_string={})
        assert res.status_code == 400


def test_create_workflow_with_name(app, session, default_user,
                                   tmp_shared_volume_path,
                                   cwl_workflow_with_name):
    """Test create workflow and its workspace by specifying a name."""
    with app.test_client() as client:
        res = client.post(url_for('api.create_workflow'),
                          query_string={
                              "user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))
        assert res.status_code == 201
        response_data = json.loads(res.get_data(as_text=True))

        # Check workflow fetch by id
        workflow_by_id = Workflow.query.filter(
            Workflow.id_ == response_data.get('workflow_id')).first()
        assert workflow_by_id

        # Check workflow fetch by name and that name of created workflow
        # is the same that was supplied to `api.create_workflow`
        workflow_by_name = Workflow.query.filter(
            Workflow.name == 'my_test_workflow').first()
        assert workflow_by_name

        workflow = workflow_by_id

        # Check that workflow workspace exist
        absolute_workflow_workspace = os.path.join(
            tmp_shared_volume_path, workflow.get_workspace())
        assert os.path.exists(absolute_workflow_workspace)


def test_create_workflow_without_name(app, session, default_user,
                                      tmp_shared_volume_path,
                                      cwl_workflow_without_name):
    """Test create workflow and its workspace without specifying a name."""
    with app.test_client() as client:
        res = client.post(url_for('api.create_workflow'),
                          query_string={
                              "user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_without_name))

        assert res.status_code == 201
        response_data = json.loads(res.get_data(as_text=True))

        # Check workflow fetch by id
        workflow_by_id = Workflow.query.filter(
            Workflow.id_ == response_data.get('workflow_id')).first()
        assert workflow_by_id

        # Check workflow fetch by name and that name of created workflow
        # is the same that was supplied to `api.create_workflow`

        import reana_workflow_controller
        default_workflow_name = reana_workflow_controller.config.\
            DEFAULT_NAME_FOR_WORKFLOWS

        workflow_by_name = Workflow.query.filter(
            Workflow.name == default_workflow_name).first()
        assert workflow_by_name

        workflow = workflow_by_id

        # Check that workflow workspace exist
        absolute_workflow_workspace = os.path.join(
            tmp_shared_volume_path, workflow.get_workspace())
        assert os.path.exists(absolute_workflow_workspace)


def test_create_workflow_wrong_user(app, session, tmp_shared_volume_path,
                                    cwl_workflow_with_name):
    """Test create workflow providing unknown user."""
    with app.test_client() as client:
        random_user_uuid = uuid.uuid4()
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": random_user_uuid},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        assert res.status_code == 404
        response_data = json.loads(res.get_data(as_text=True))
        workflow = Workflow.query.filter(
            Workflow.id_ == response_data.get('workflow_id')).first()
        # workflow exist in DB
        assert not workflow


def test_download_missing_file(app, default_user,
                               cwl_workflow_with_name):
    """Test download missing file."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        assert res.status_code == 201
        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        file_name = 'input.csv'
        res = client.get(
            url_for('api.download_file',
                    workflow_id_or_name=workflow_uuid,
                    file_name=file_name),
            query_string={"user": default_user.id_},
            content_type='application/json',
            data=json.dumps(cwl_workflow_with_name))

        assert res.status_code == 404
        response_data = json.loads(res.get_data(as_text=True))
        assert response_data == {'message': 'input.csv does not exist.'}


def test_download_file(app, session, default_user,
                       tmp_shared_volume_path,
                       cwl_workflow_with_name):
    """Test download file from workspace."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_uuid).first()
        # create file
        file_name = 'output name.csv'
        file_binary_content = b'1,2,3,4\n5,6,7,8'
        # write file in the workflow workspace under `outputs` directory:
        # we use `secure_filename` here because
        # we use it in server side when adding
        # files
        absolute_path_workflow_workspace = \
            os.path.join(tmp_shared_volume_path,
                         workflow.get_workspace())
        file_path = os.path.join(absolute_path_workflow_workspace,
                                 file_name)
        # because outputs directory doesn't exist by default
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb+') as f:
            f.write(file_binary_content)
        res = client.get(
            url_for('api.download_file',
                    workflow_id_or_name=workflow_uuid,
                    file_name=file_name),
            query_string={"user": default_user.id_},
            content_type='application/json',
            data=json.dumps(cwl_workflow_with_name))
        assert res.data == file_binary_content


def test_download_file_with_path(app, session, default_user,
                                 tmp_shared_volume_path,
                                 cwl_workflow_with_name):
    """Test download file prepended with path."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_uuid).first()
        # create file
        file_name = 'first/1991/output.csv'
        file_binary_content = b'1,2,3,4\n5,6,7,8'
        # write file in the workflow workspace under `outputs` directory:
        # we use `secure_filename` here because
        # we use it in server side when adding
        # files
        absolute_path_workflow_workspace = \
            os.path.join(tmp_shared_volume_path,
                         workflow.get_workspace())
        file_path = os.path.join(absolute_path_workflow_workspace, file_name)
        # because outputs directory doesn't exist by default
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb+') as f:
            f.write(file_binary_content)
        res = client.get(
            url_for('api.download_file',
                    workflow_id_or_name=workflow_uuid,
                    file_name=file_name),
            query_string={"user": default_user.id_},
            content_type='application/json',
            data=json.dumps(cwl_workflow_with_name))
        assert res.data == file_binary_content


def test_get_files(app, session, default_user,
                   tmp_shared_volume_path,
                   cwl_workflow_with_name):
    """Test get files list."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_uuid).first()
        # create file
        absolute_path_workflow_workspace = \
            os.path.join(tmp_shared_volume_path,
                         workflow.get_workspace())
        fs_ = fs.open_fs(absolute_path_workflow_workspace)
        test_files = []
        for i in range(5):
            file_name = '{0}.csv'.format(i)
            subdir_name = str(uuid.uuid4())
            subdir = fs.path.join(subdir_name)
            fs_.makedirs(subdir)
            fs_.touch('{0}/{1}'.format(subdir, file_name))
            test_files.append(os.path.join(subdir_name, file_name))

        res = client.get(
            url_for('api.get_files',
                    workflow_id_or_name=workflow_uuid),
            query_string={"user": default_user.id_},
            content_type='application/json',
            data=json.dumps(cwl_workflow_with_name))
        for file_ in json.loads(res.data.decode()):
            assert file_.get('name') in test_files


def test_get_files_unknown_workflow(app, default_user):
    """Test get list of files for non existing workflow."""
    with app.test_client() as client:
        # create workflow
        random_workflow_uuid = str(uuid.uuid4())

        res = client.get(
            url_for('api.get_files',
                    workflow_id_or_name=random_workflow_uuid),
            query_string={"user": default_user.id_},
            content_type='application/json')

        assert res.status_code == 404
        response_data = json.loads(res.get_data(as_text=True))
        expected_data = {'message': 'REANA_WORKON is set to {0}, but '
                                    'that workflow does not exist. '
                                    'Please set your REANA_WORKON environment '
                                    'variable appropriately.'.
                         format(random_workflow_uuid)}
        assert response_data == expected_data


def test_get_workflow_status_with_uuid(app, session, default_user,
                                       cwl_workflow_with_name):
    """Test get workflow status."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_uuid).first()

        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        json_response = json.loads(res.data.decode())
        assert json_response.get('status') == workflow.status.name
        workflow.status = WorkflowStatus.finished
        session.commit()

        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        json_response = json.loads(res.data.decode())
        assert json_response.get('status') == workflow.status.name


def test_get_workflow_status_with_name(app, session, default_user,
                                       cwl_workflow_with_name):
    """Test get workflow status."""
    with app.test_client() as client:
        # create workflow
        workflow_uuid = uuid.uuid4()
        workflow_name = 'my_test_workflow'
        workflow = Workflow(
            id_=workflow_uuid,
            name=workflow_name,
            status=WorkflowStatus.finished,
            owner_id=default_user.id_,
            reana_specification=cwl_workflow_with_name['reana_specification'],
            type_=cwl_workflow_with_name[
                'reana_specification']['type'],
            logs='')
        session.add(workflow)
        session.commit()

        workflow = Workflow.query.filter(
            Workflow.name == workflow_name).first()

        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=workflow_name + '.1'),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        json_response = json.loads(res.data.decode())

        assert json_response.get('status') == workflow.status.name
        workflow.status = WorkflowStatus.finished
        session.commit()

        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=workflow_name + '.1'),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        json_response = json.loads(res.data.decode())
        assert json_response.get('status') == workflow.status.name


def test_get_workflow_status_unauthorized(app, default_user,
                                          cwl_workflow_with_name):
    """Test get workflow status unauthorized."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_created_uuid = response_data.get('workflow_id')
        random_user_uuid = uuid.uuid4()
        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=workflow_created_uuid),
                         query_string={"user": random_user_uuid},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        assert res.status_code == 403


def test_get_workflow_status_unknown_workflow(app, default_user,
                                              cwl_workflow_with_name):
    """Test get workflow status for unknown workflow."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))
        random_workflow_uuid = uuid.uuid4()
        res = client.get(url_for('api.get_workflow_status',
                                 workflow_id_or_name=random_workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(cwl_workflow_with_name))
        assert res.status_code == 404


def test_set_workflow_status(app, session, default_user,
                             yadage_workflow_with_name):
    """Test set workflow status "Start"."""
    with app.test_client() as client:
        os.environ["TESTS"] = "True"
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_created_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_created_uuid).first()
        assert workflow.status == WorkflowStatus.created
        payload = START
        # replace celery task with Mock()
        with mock.patch('reana_workflow_controller.tasks.run_yadage_workflow'
                        '.apply_async') as celery_mock:
            # set workflow status to START
            res = client.put(url_for('api.set_workflow_status',
                             workflow_id_or_name=workflow_created_uuid),
                             query_string={"user": default_user.id_,
                                           "status": "start"})
            json_response = json.loads(res.data.decode())
            assert json_response.get('status') == status_dict[payload].name
            # assert the celery task was called with the following arguments
            celery_mock.assert_called_with(
                kwargs={'workflow_uuid': workflow_created_uuid,
                        'workflow_workspace':
                        'users/{user_id}/workflows/{workflow_uuid}'.
                        format(user_id=default_user.id_,
                               workflow_uuid=workflow_created_uuid),
                        'workflow_json': yadage_workflow_with_name[
                            'reana_specification']['workflow'][
                                'specification'],
                        'parameters': {}},
                queue='yadage-default-queue')


def test_start_already_started_workflow(app, session, default_user,
                                        yadage_workflow_with_name):
    """Test start workflow twice."""
    with app.test_client() as client:
        os.environ["TESTS"] = "True"
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_created_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_created_uuid).first()
        assert workflow.status == WorkflowStatus.created
        payload = START
        # replace celery task with Mock()
        with mock.patch('reana_workflow_controller.tasks.run_yadage_workflow'
                        '.apply_async') as celery_mock:
            # set workflow status to START
            res = client.put(url_for('api.set_workflow_status',
                             workflow_id_or_name=workflow_created_uuid),
                             query_string={"user": default_user.id_,
                                           "status": "start"})
            json_response = json.loads(res.data.decode())
            assert json_response.get('status') == status_dict[payload].name
            # assert the celery task was called with the following arguments
            celery_mock.assert_called_with(
                kwargs={'workflow_uuid': workflow_created_uuid,
                        'workflow_workspace':
                        'users/{user_id}/workflows/{workflow_uuid}'.
                        format(user_id=default_user.id_,
                               workflow_uuid=workflow_created_uuid),
                        'workflow_json': yadage_workflow_with_name[
                            'reana_specification']['workflow'][
                                'specification'],
                        'parameters': {}},
                queue='yadage-default-queue')
            res = client.put(url_for('api.set_workflow_status',
                             workflow_id_or_name=workflow_created_uuid),
                             query_string={"user": default_user.id_,
                                           "status": "start"})
            json_response = json.loads(res.data.decode())
            assert res.status_code == 409
            expected_message = ("Workflow {0} could not be started because"
                                " it is already running.").format(
                                    workflow_created_uuid)
            assert json_response.get('message') == expected_message


def test_set_workflow_status_unauthorized(app, default_user,
                                          yadage_workflow_with_name):
    """Test set workflow status unauthorized."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_created_uuid = response_data.get('workflow_id')
        random_user_uuid = uuid.uuid4()
        payload = START
        res = client.put(url_for('api.set_workflow_status',
                                 workflow_id_or_name=workflow_created_uuid),
                         query_string={"user": random_user_uuid,
                                       "status": payload},
                         content_type='application/json')
        assert res.status_code == 403


def test_set_workflow_status_unknown_workflow(app, default_user,
                                              yadage_workflow_with_name):
    """Test set workflow status for unknown workflow."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))
        random_workflow_uuid = uuid.uuid4()
        payload = START
        res = client.put(url_for('api.set_workflow_status',
                                 workflow_id_or_name=random_workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json',
                         data=json.dumps(payload))
        assert res.status_code == 404


def test_upload_file(app, session, default_user,
                     tmp_shared_volume_path,
                     cwl_workflow_with_name):
    """Test upload file."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))

        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow = Workflow.query.filter(
            Workflow.id_ == workflow_uuid).first()
        # create file
        file_name = 'dataset.csv'
        file_binary_content = b'1,2,3,4\n5,6,7,8'

        res = client.post(
            url_for('api.upload_file',
                    workflow_id_or_name=workflow_uuid),
            query_string={"user": default_user.id_,
                          "file_name": file_name},
            content_type='multipart/form-data',
            data={'file_content': (io.BytesIO(file_binary_content),
                                   file_name)})
        assert res.status_code == 200
        # remove workspace directory from path
        workflow_workspace = workflow.get_workspace()

        # we use `secure_filename` here because
        # we use it in server side when adding
        # files
        absolute_file_path = os.path.join(tmp_shared_volume_path,
                                          workflow_workspace,
                                          secure_filename(file_name))

        with open(absolute_file_path, 'rb') as f:
            assert f.read() == file_binary_content


def test_upload_file_unknown_workflow(app, default_user):
    """Test upload file to non existing workflow."""
    with app.test_client() as client:
        random_workflow_uuid = uuid.uuid4()
        # create file
        file_name = 'dataset.csv'
        file_binary_content = b'1,2,3,4\n5,6,7,8'

        res = client.post(
            url_for('api.upload_file',
                    workflow_id_or_name=random_workflow_uuid),
            query_string={"user": default_user.id_,
                          "file_name": file_name},
            content_type='multipart/form-data',
            data={'file_content': (io.BytesIO(file_binary_content),
                                   file_name)})
        assert res.status_code == 404


def test_get_created_workflow_logs(app, default_user, cwl_workflow_with_name):
    """Test get workflow logs."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(cwl_workflow_with_name))
        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        workflow_name = response_data.get('workflow_name')
        res = client.get(url_for('api.get_workflow_logs',
                                 workflow_id_or_name=workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json')
        assert res.status_code == 200
        response_data = json.loads(res.get_data(as_text=True))
        create_workflow_logs = ""
        expected_data = {
            'workflow_id': workflow_uuid,
            'workflow_name': workflow_name,
            'user': str(default_user.id_),
            'logs': create_workflow_logs
        }
        assert response_data == expected_data


def test_get_unknown_workflow_logs(app, default_user,
                                   yadage_workflow_with_name):
    """Test set workflow status for unknown workflow."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))
        random_workflow_uuid = uuid.uuid4()
        res = client.get(url_for('api.get_workflow_logs',
                                 workflow_id_or_name=random_workflow_uuid),
                         query_string={"user": default_user.id_},
                         content_type='application/json')
        assert res.status_code == 404


def test_get_workflow_logs_unauthorized(app, default_user,
                                        yadage_workflow_with_name):
    """Test set workflow status for unknown workflow."""
    with app.test_client() as client:
        # create workflow
        res = client.post(url_for('api.create_workflow'),
                          query_string={"user": default_user.id_},
                          content_type='application/json',
                          data=json.dumps(yadage_workflow_with_name))
        response_data = json.loads(res.get_data(as_text=True))
        workflow_uuid = response_data.get('workflow_id')
        random_user_uuid = uuid.uuid4()
        res = client.get(url_for('api.get_workflow_logs',
                                 workflow_id_or_name=workflow_uuid),
                         query_string={"user": random_user_uuid},
                         content_type='application/json')
        assert res.status_code == 403
