"""
Azure VM Lifecycle Management
Provisions, configures, and tears down test VMs
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import time
import logging

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError

from ..utils.config import AzureConfig, VMConfig
from ..utils.helpers import generate_vm_name, wait_for_condition

logger = logging.getLogger(__name__)


class AzureVMManager:
    """
    Manages Azure VM lifecycle for CDR testing

    Handles:
    - VM provisioning (with Spot instances for cost savings)
    - Snapshot creation for rollback
    - VM configuration
    - Cleanup and teardown
    """

    def __init__(self, azure_config: AzureConfig, vm_config: VMConfig):
        """
        Initialize Azure VM Manager

        Args:
            azure_config: Azure infrastructure configuration
            vm_config: VM configuration
        """
        self.azure_config = azure_config
        self.vm_config = vm_config

        # Initialize Azure clients
        self.credential = DefaultAzureCredential()
        self.compute_client = ComputeManagementClient(
            credential=self.credential,
            subscription_id=azure_config.subscription_id
        )
        self.network_client = NetworkManagementClient(
            credential=self.credential,
            subscription_id=azure_config.subscription_id
        )
        self.resource_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=azure_config.subscription_id
        )

        self.logger = logging.getLogger(__name__)

    def provision_vm(
        self,
        test_run_id: str,
        vm_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Provision a new test VM

        Args:
            test_run_id: Unique test run identifier
            vm_name: Optional VM name (auto-generated if not provided)

        Returns:
            VM information
        """
        if not vm_name:
            vm_name = generate_vm_name("cdr-test", test_run_id)

        self.logger.info(f"Provisioning VM: {vm_name}")

        try:
            # Create network interface
            nic_name = f"{vm_name}-nic"
            nic = self._create_network_interface(nic_name)

            # Create VM
            vm_parameters = self._build_vm_parameters(vm_name, nic.id)

            # Start async VM creation
            vm_creation = self.compute_client.virtual_machines.begin_create_or_update(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name,
                parameters=vm_parameters
            )

            self.logger.info(f"Creating VM {vm_name}... (this may take 3-5 minutes)")

            # Wait for completion
            vm = vm_creation.result()

            self.logger.info(f"VM {vm_name} created successfully")

            # Get VM details
            vm_info = self.get_vm_info(vm_name)

            return vm_info

        except Exception as e:
            self.logger.error(f"Failed to provision VM: {e}", exc_info=True)
            raise

    def _create_network_interface(self, nic_name: str) -> Any:
        """Create network interface for VM"""
        self.logger.info(f"Creating network interface: {nic_name}")

        nic_parameters = {
            'location': self.azure_config.location,
            'ip_configurations': [{
                'name': f"{nic_name}-ipconfig",
                'subnet': {'id': self.azure_config.test_vm_subnet_id},
                'private_ip_allocation_method': 'Dynamic'
            }]
        }

        nic_creation = self.network_client.network_interfaces.begin_create_or_update(
            resource_group_name=self.azure_config.resource_group,
            network_interface_name=nic_name,
            parameters=nic_parameters
        )

        return nic_creation.result()

    def _build_vm_parameters(self, vm_name: str, nic_id: str) -> Dict[str, Any]:
        """Build VM creation parameters"""
        vm_parameters = {
            'location': self.azure_config.location,
            'hardware_profile': {
                'vm_size': self.vm_config.vm_size
            },
            'storage_profile': {
                'image_reference': {
                    'publisher': self.vm_config.image_publisher,
                    'offer': self.vm_config.image_offer,
                    'sku': self.vm_config.image_sku,
                    'version': self.vm_config.image_version
                },
                'os_disk': {
                    'name': f"{vm_name}-osdisk",
                    'caching': 'ReadWrite',
                    'create_option': 'FromImage',
                    'managed_disk': {
                        'storage_account_type': 'Standard_LRS'
                    },
                    'disk_size_gb': self.vm_config.os_disk_size_gb
                }
            },
            'os_profile': {
                'computer_name': vm_name,
                'admin_username': self.vm_config.admin_username,
                'admin_password': self.vm_config.admin_password,
                'windows_configuration': {
                    'enable_automatic_updates': False,
                    'provision_vm_agent': True
                }
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': nic_id,
                    'properties': {
                        'primary': True
                    }
                }]
            },
            'tags': {
                'purpose': 'cdr-testing',
                'auto-delete': 'true',
                'created': datetime.now().isoformat()
            }
        }

        # Add Spot instance configuration if enabled
        if self.vm_config.use_spot_instances:
            vm_parameters['priority'] = 'Spot'
            vm_parameters['eviction_policy'] = 'Deallocate'
            vm_parameters['billing_profile'] = {
                'max_price': self.vm_config.spot_max_price
            }

        return vm_parameters

    def get_vm_info(self, vm_name: str) -> Dict[str, Any]:
        """
        Get VM information

        Args:
            vm_name: Name of the VM

        Returns:
            VM details
        """
        try:
            vm = self.compute_client.virtual_machines.get(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name,
                expand='instanceView'
            )

            # Get network interface details for IP
            nic_id = vm.network_profile.network_interfaces[0].id
            nic_name = nic_id.split('/')[-1]

            nic = self.network_client.network_interfaces.get(
                resource_group_name=self.azure_config.resource_group,
                network_interface_name=nic_name
            )

            private_ip = nic.ip_configurations[0].private_ip_address

            # Get power state
            power_state = 'unknown'
            if vm.instance_view and vm.instance_view.statuses:
                for status in vm.instance_view.statuses:
                    if status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]

            return {
                'vm_name': vm_name,
                'vm_id': vm.id,
                'location': vm.location,
                'vm_size': vm.hardware_profile.vm_size,
                'power_state': power_state,
                'private_ip': private_ip,
                'os_type': vm.storage_profile.os_disk.os_type,
                'provisioning_state': vm.provisioning_state
            }

        except ResourceNotFoundError:
            self.logger.error(f"VM {vm_name} not found")
            return None
        except Exception as e:
            self.logger.error(f"Error getting VM info: {e}")
            return None

    def wait_for_vm_ready(self, vm_name: str, timeout: int = 600) -> bool:
        """
        Wait for VM to be fully ready

        Args:
            vm_name: Name of the VM
            timeout: Maximum wait time in seconds

        Returns:
            True if VM is ready
        """
        self.logger.info(f"Waiting for VM {vm_name} to be ready...")

        def is_ready():
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                return False

            return (
                vm_info['provisioning_state'] == 'Succeeded' and
                vm_info['power_state'] == 'running'
            )

        try:
            wait_for_condition(
                condition_func=is_ready,
                timeout_seconds=timeout,
                poll_interval=10,
                error_message=f"VM {vm_name} not ready within {timeout}s"
            )
            self.logger.info(f"VM {vm_name} is ready")
            return True

        except TimeoutError as e:
            self.logger.error(str(e))
            return False

    def create_snapshot(self, vm_name: str) -> Optional[str]:
        """
        Create snapshot of VM's OS disk

        Args:
            vm_name: Name of the VM

        Returns:
            Snapshot ID
        """
        self.logger.info(f"Creating snapshot for VM {vm_name}")

        try:
            vm = self.compute_client.virtual_machines.get(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name
            )

            os_disk_name = vm.storage_profile.os_disk.name
            snapshot_name = f"{vm_name}-snapshot-{int(time.time())}"

            disk = self.compute_client.disks.get(
                resource_group_name=self.azure_config.resource_group,
                disk_name=os_disk_name
            )

            snapshot_params = {
                'location': self.azure_config.location,
                'creation_data': {
                    'create_option': 'Copy',
                    'source_resource_id': disk.id
                }
            }

            snapshot_creation = self.compute_client.snapshots.begin_create_or_update(
                resource_group_name=self.azure_config.resource_group,
                snapshot_name=snapshot_name,
                snapshot=snapshot_params
            )

            snapshot = snapshot_creation.result()
            self.logger.info(f"Snapshot created: {snapshot_name}")

            return snapshot.id

        except Exception as e:
            self.logger.error(f"Failed to create snapshot: {e}")
            return None

    def delete_vm(self, vm_name: str, delete_disks: bool = True) -> bool:
        """
        Delete VM and associated resources

        Args:
            vm_name: Name of the VM
            delete_disks: Whether to delete associated disks

        Returns:
            True if deletion successful
        """
        self.logger.info(f"Deleting VM: {vm_name}")

        try:
            # Get VM info before deletion to get resource IDs
            vm = self.compute_client.virtual_machines.get(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name
            )

            os_disk_name = vm.storage_profile.os_disk.name
            nic_id = vm.network_profile.network_interfaces[0].id
            nic_name = nic_id.split('/')[-1]

            # Delete VM
            self.logger.info(f"Deleting VM {vm_name}...")
            vm_deletion = self.compute_client.virtual_machines.begin_delete(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name
            )
            vm_deletion.wait()

            # Delete network interface
            self.logger.info(f"Deleting NIC {nic_name}...")
            nic_deletion = self.network_client.network_interfaces.begin_delete(
                resource_group_name=self.azure_config.resource_group,
                network_interface_name=nic_name
            )
            nic_deletion.wait()

            # Delete OS disk if requested
            if delete_disks:
                self.logger.info(f"Deleting OS disk {os_disk_name}...")
                disk_deletion = self.compute_client.disks.begin_delete(
                    resource_group_name=self.azure_config.resource_group,
                    disk_name=os_disk_name
                )
                disk_deletion.wait()

            self.logger.info(f"VM {vm_name} and associated resources deleted")
            return True

        except ResourceNotFoundError:
            self.logger.warning(f"VM {vm_name} not found (already deleted?)")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting VM: {e}")
            return False

    def execute_command(self, vm_name: str, command: str) -> Dict[str, Any]:
        """
        Execute command on VM using Azure Run Command

        Args:
            vm_name: Name of the VM
            command: Command to execute

        Returns:
            Command output
        """
        self.logger.info(f"Executing command on {vm_name}: {command}")

        try:
            run_command_params = {
                'command_id': 'RunPowerShellScript',
                'script': [command]
            }

            operation = self.compute_client.virtual_machines.begin_run_command(
                resource_group_name=self.azure_config.resource_group,
                vm_name=vm_name,
                parameters=run_command_params
            )

            result = operation.result()

            return {
                'success': True,
                'output': result.value[0].message if result.value else '',
                'error': result.value[1].message if len(result.value) > 1 else ''
            }

        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def list_test_vms(self) -> List[Dict[str, Any]]:
        """
        List all CDR test VMs

        Returns:
            List of test VMs
        """
        try:
            vms = self.compute_client.virtual_machines.list(
                resource_group_name=self.azure_config.resource_group
            )

            test_vms = []
            for vm in vms:
                if vm.tags and vm.tags.get('purpose') == 'cdr-testing':
                    test_vms.append({
                        'name': vm.name,
                        'location': vm.location,
                        'vm_size': vm.hardware_profile.vm_size,
                        'created': vm.tags.get('created'),
                        'provisioning_state': vm.provisioning_state
                    })

            return test_vms

        except Exception as e:
            self.logger.error(f"Error listing VMs: {e}")
            return []
