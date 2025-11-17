"""
VM Pool Manager for Phase 3 EDR Testing
Manages a pool of VMs with pre-installed EDR agents
Handles VM provisioning, allocation, cleanup, and recycling
"""

import logging
import threading
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from queue import Queue, Empty
from dataclasses import dataclass

from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute.models import RunCommandInput

logger = logging.getLogger(__name__)


@dataclass
class VMInfo:
    """Information about a VM in the pool"""
    vm_name: str
    resource_group: str
    edr_solution: str  # crowdstrike, sentinelone, sophos
    status: str  # available, in_use, cleaning, provisioning
    public_ip: str
    private_ip: str
    created_at: datetime
    last_used_at: Optional[datetime]
    use_count: int


class VMPoolManager:
    """
    Manages a pool of VMs with pre-installed EDR agents

    Features:
    - Pre-provisions VMs from base images
    - Maintains separate pools for each EDR solution
    - Handles VM allocation and release
    - Automatic VM cleaning between tests
    - VM recycling after N uses (prevents agent issues)
    - Concurrent VM management with thread-safe queues
    """

    def __init__(self, config_manager):
        """
        Initialize VM Pool Manager

        Args:
            config_manager: Configuration manager
        """
        self.config = config_manager.load_vm_config()
        self.azure_config = config_manager.load_azure_config()

        # Azure clients
        self.credential = DefaultAzureCredential()
        self.compute_client = ComputeManagementClient(
            self.credential,
            self.azure_config['subscription_id']
        )
        self.network_client = NetworkManagementClient(
            self.credential,
            self.azure_config['subscription_id']
        )

        # VM pools (separate queue for each EDR solution)
        self.pools = {
            'crowdstrike': Queue(),
            'sentinelone': Queue(),
            'sophos': Queue()
        }

        # Track all VMs
        self.all_vms = {}  # vm_name -> VMInfo
        self.vm_lock = threading.Lock()

        # Pool configuration
        self.pool_size_per_edr = self.config.get('pool_size', 5)  # 5 VMs per EDR = 15 total
        self.max_vm_uses = self.config.get('max_vm_uses', 20)  # Recycle after 20 uses
        self.vm_clean_timeout = self.config.get('vm_clean_timeout', 120)  # 2 min cleanup

        # Base image references (you'll need to create these)
        self.base_images = {
            'crowdstrike': self.config.get('crowdstrike_image_id'),
            'sentinelone': self.config.get('sentinelone_image_id'),
            'sophos': self.config.get('sophos_image_id')
        }

        logger.info(
            f"Initialized VM Pool Manager: {self.pool_size_per_edr} VMs per EDR solution "
            f"({self.pool_size_per_edr * 3} total)"
        )

    def initialize_pools(self):
        """
        Pre-provision VMs for all pools
        Should be called at application startup
        """
        logger.info("Initializing VM pools...")

        threads = []
        for edr_solution in ['crowdstrike', 'sentinelone', 'sophos']:
            thread = threading.Thread(
                target=self._provision_pool,
                args=(edr_solution,)
            )
            thread.start()
            threads.append(thread)

        # Wait for all pools to initialize
        for thread in threads:
            thread.join()

        logger.info(f"VM pools initialized. Total VMs: {len(self.all_vms)}")

    def _provision_pool(self, edr_solution: str):
        """Provision VMs for a specific EDR solution pool"""
        logger.info(f"Provisioning {self.pool_size_per_edr} VMs for {edr_solution}")

        for i in range(self.pool_size_per_edr):
            try:
                vm_name = f"edr-test-{edr_solution}-{i:02d}-{int(time.time())}"
                vm_info = self._provision_vm(vm_name, edr_solution)

                with self.vm_lock:
                    self.all_vms[vm_name] = vm_info

                self.pools[edr_solution].put(vm_info)
                logger.info(f"Provisioned VM {vm_name} for {edr_solution}")

            except Exception as e:
                logger.error(f"Failed to provision VM for {edr_solution}: {e}", exc_info=True)

    def _provision_vm(self, vm_name: str, edr_solution: str) -> VMInfo:
        """
        Provision a single VM from base image

        Args:
            vm_name: Name for the VM
            edr_solution: EDR solution (determines which base image to use)

        Returns:
            VMInfo object
        """
        resource_group = self.azure_config['resource_group']
        location = self.azure_config['location']
        base_image_id = self.base_images.get(edr_solution)

        if not base_image_id:
            raise ValueError(f"No base image configured for {edr_solution}")

        logger.info(f"Provisioning VM {vm_name} from image {base_image_id}")

        # Create VM from managed image
        # This is simplified - in production you'd handle networking, disks, etc.
        vm_parameters = {
            'location': location,
            'storage_profile': {
                'image_reference': {
                    'id': base_image_id
                }
            },
            'hardware_profile': {
                'vm_size': self.config.get('vm_size', 'Standard_D2s_v3')
            },
            'os_profile': {
                'computer_name': vm_name,
                'admin_username': self.config['admin_username'],
                'admin_password': self.config['admin_password']
            },
            'network_profile': {
                'network_interfaces': [{
                    'id': self._create_nic(vm_name, resource_group, location),
                    'properties': {
                        'primary': True
                    }
                }]
            },
            'priority': 'Spot',  # Use Spot VMs for cost savings
            'eviction_policy': 'Deallocate',
            'billing_profile': {
                'max_price': -1  # Pay up to regular price
            }
        }

        # Create VM (async operation)
        async_vm_creation = self.compute_client.virtual_machines.begin_create_or_update(
            resource_group,
            vm_name,
            vm_parameters
        )

        # Wait for completion
        vm = async_vm_creation.result()

        # Get IP addresses
        public_ip, private_ip = self._get_vm_ips(vm_name, resource_group)

        return VMInfo(
            vm_name=vm_name,
            resource_group=resource_group,
            edr_solution=edr_solution,
            status='available',
            public_ip=public_ip,
            private_ip=private_ip,
            created_at=datetime.now(),
            last_used_at=None,
            use_count=0
        )

    def _create_nic(self, vm_name: str, resource_group: str, location: str) -> str:
        """Create network interface for VM"""
        # Simplified - assumes vnet/subnet already exist
        nic_name = f"{vm_name}-nic"
        subnet_id = self.config['subnet_id']

        nic_params = {
            'location': location,
            'ip_configurations': [{
                'name': f"{vm_name}-ipconfig",
                'subnet': {'id': subnet_id},
                'public_ip_address': {
                    'id': self._create_public_ip(vm_name, resource_group, location)
                }
            }]
        }

        nic = self.network_client.network_interfaces.begin_create_or_update(
            resource_group,
            nic_name,
            nic_params
        ).result()

        return nic.id

    def _create_public_ip(self, vm_name: str, resource_group: str, location: str) -> str:
        """Create public IP for VM"""
        ip_name = f"{vm_name}-ip"

        public_ip_params = {
            'location': location,
            'public_ip_allocation_method': 'Dynamic'
        }

        public_ip = self.network_client.public_ip_addresses.begin_create_or_update(
            resource_group,
            ip_name,
            public_ip_params
        ).result()

        return public_ip.id

    def _get_vm_ips(self, vm_name: str, resource_group: str) -> tuple:
        """Get public and private IPs for VM"""
        vm = self.compute_client.virtual_machines.get(resource_group, vm_name)
        nic_id = vm.network_profile.network_interfaces[0].id
        nic_name = nic_id.split('/')[-1]

        nic = self.network_client.network_interfaces.get(resource_group, nic_name)
        private_ip = nic.ip_configurations[0].private_ip_address

        public_ip_id = nic.ip_configurations[0].public_ip_address.id
        public_ip_name = public_ip_id.split('/')[-1]
        public_ip = self.network_client.public_ip_addresses.get(resource_group, public_ip_name)

        return public_ip.ip_address, private_ip

    def acquire_vm(self, edr_solution: str, timeout: int = 3600) -> Dict[str, Any]:
        """
        Acquire a VM from the pool for testing

        Blocks until a VM is available (with timeout)

        Args:
            edr_solution: EDR solution needed (crowdstrike, sentinelone, sophos)
            timeout: Max seconds to wait for VM (default 1 hour)

        Returns:
            VM info dict

        Raises:
            TimeoutError: If no VM available within timeout
        """
        logger.info(f"Acquiring {edr_solution} VM from pool (timeout: {timeout}s)")

        try:
            # Wait for VM from queue
            vm_info = self.pools[edr_solution].get(timeout=timeout)

            # Update VM status
            with self.vm_lock:
                vm_info.status = 'in_use'
                vm_info.last_used_at = datetime.now()
                vm_info.use_count += 1

            logger.info(f"Acquired VM {vm_info.vm_name} (use count: {vm_info.use_count})")

            return {
                'vm_name': vm_info.vm_name,
                'resource_group': vm_info.resource_group,
                'public_ip': vm_info.public_ip,
                'private_ip': vm_info.private_ip,
                'edr_solution': vm_info.edr_solution
            }

        except Empty:
            logger.error(f"Timeout waiting for {edr_solution} VM after {timeout}s")
            raise TimeoutError(f"No {edr_solution} VM available within {timeout}s")

    def release_vm(self, vm: Dict[str, Any], clean: bool = True):
        """
        Release VM back to pool

        Args:
            vm: VM info dict (from acquire_vm)
            clean: Whether to clean VM before returning to pool
        """
        vm_name = vm['vm_name']
        edr_solution = vm['edr_solution']

        logger.info(f"Releasing VM {vm_name} (clean: {clean})")

        with self.vm_lock:
            vm_info = self.all_vms.get(vm_name)
            if not vm_info:
                logger.error(f"VM {vm_name} not found in tracking")
                return

            # Check if VM should be recycled
            if vm_info.use_count >= self.max_vm_uses:
                logger.info(f"VM {vm_name} reached max uses ({self.max_vm_uses}), recycling...")
                self._recycle_vm(vm_info)
                return

            # Clean VM if requested
            if clean:
                vm_info.status = 'cleaning'
                threading.Thread(target=self._clean_and_return_vm, args=(vm_info,)).start()
            else:
                vm_info.status = 'available'
                self.pools[edr_solution].put(vm_info)

    def _clean_and_return_vm(self, vm_info: VMInfo):
        """Clean VM and return to pool"""
        try:
            logger.info(f"Cleaning VM {vm_info.vm_name}")

            # Run cleanup script on VM
            self._run_cleanup_script(vm_info)

            # Wait for cleanup to complete
            time.sleep(10)

            # Return to pool
            with self.vm_lock:
                vm_info.status = 'available'

            self.pools[vm_info.edr_solution].put(vm_info)
            logger.info(f"VM {vm_info.vm_name} cleaned and returned to pool")

        except Exception as e:
            logger.error(f"Error cleaning VM {vm_info.vm_name}: {e}", exc_info=True)
            # If cleaning fails, recycle the VM
            self._recycle_vm(vm_info)

    def _run_cleanup_script(self, vm_info: VMInfo):
        """Run cleanup script on VM via Azure Run Command"""
        cleanup_script = """
        # Delete test files
        Remove-Item C:\\test-files\\* -Recurse -Force -ErrorAction SilentlyContinue

        # Clear temp files
        Remove-Item $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue

        # Clear download folder
        Remove-Item C:\\Users\\*\\Downloads\\* -Recurse -Force -ErrorAction SilentlyContinue

        # Clear recent files
        Remove-Item "$env:APPDATA\\Microsoft\\Windows\\Recent\\*" -Force -ErrorAction SilentlyContinue
        """

        command = RunCommandInput(
            command_id='RunPowerShellScript',
            script=[cleanup_script]
        )

        self.compute_client.virtual_machines.begin_run_command(
            vm_info.resource_group,
            vm_info.vm_name,
            command
        ).result()

    def _recycle_vm(self, vm_info: VMInfo):
        """Delete and replace VM with fresh one"""
        logger.info(f"Recycling VM {vm_info.vm_name}")

        try:
            # Delete old VM
            self._delete_vm(vm_info)

            # Provision new VM
            new_vm_name = f"edr-test-{vm_info.edr_solution}-{int(time.time())}"
            new_vm_info = self._provision_vm(new_vm_name, vm_info.edr_solution)

            # Update tracking
            with self.vm_lock:
                del self.all_vms[vm_info.vm_name]
                self.all_vms[new_vm_name] = new_vm_info

            # Add to pool
            self.pools[vm_info.edr_solution].put(new_vm_info)

            logger.info(f"Recycled VM: {vm_info.vm_name} -> {new_vm_name}")

        except Exception as e:
            logger.error(f"Error recycling VM {vm_info.vm_name}: {e}", exc_info=True)

    def _delete_vm(self, vm_info: VMInfo):
        """Delete VM and associated resources"""
        logger.info(f"Deleting VM {vm_info.vm_name}")

        # Delete VM
        self.compute_client.virtual_machines.begin_delete(
            vm_info.resource_group,
            vm_info.vm_name
        ).result()

        # Note: In production, also delete NIC, public IP, disks, etc.

    def copy_file_to_vm(self, vm: Dict[str, Any], local_file_path: str) -> str:
        """
        Copy file to VM

        Args:
            vm: VM info dict
            local_file_path: Local file path

        Returns:
            Remote file path on VM
        """
        # In production, use SCP, Azure Files, or storage account
        # For now, use Run Command to download from blob
        # This is simplified

        remote_path = f"C:\\test-files\\{local_file_path.split('/')[-1]}"
        logger.info(f"Copying file to VM {vm['vm_name']}: {remote_path}")

        # Implementation would use Azure Run Command to download from blob
        # or SCP/WinRM to copy directly

        return remote_path

    def execute_file_on_vm(
        self,
        vm: Dict[str, Any],
        remote_file_path: str,
        duration_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Execute file on VM with user simulation

        Args:
            vm: VM info dict
            remote_file_path: Path to file on VM
            duration_seconds: How long to run file interaction

        Returns:
            Execution result
        """
        logger.info(f"Executing file on VM {vm['vm_name']}: {remote_file_path}")

        # Run file execution script via Azure Run Command
        execution_script = f"""
        $file = "{remote_file_path}"

        # Execute file based on extension
        if ($file -like "*.exe" -or $file -like "*.dll") {{
            Start-Process $file
        }}
        elseif ($file -like "*.docx" -or $file -like "*.xlsx" -or $file -like "*.pptx") {{
            Start-Process $file
        }}
        elseif ($file -like "*.pdf") {{
            Start-Process $file
        }}

        # Wait for duration
        Start-Sleep -Seconds {duration_seconds}
        """

        command = RunCommandInput(
            command_id='RunPowerShellScript',
            script=[execution_script]
        )

        result = self.compute_client.virtual_machines.begin_run_command(
            vm['resource_group'],
            vm['vm_name'],
            command
        ).result()

        return {
            'success': True,
            'output': result.value[0].message if result.value else None
        }

    def shutdown_pools(self):
        """Shutdown all VM pools (delete all VMs)"""
        logger.info("Shutting down VM pools...")

        with self.vm_lock:
            for vm_info in list(self.all_vms.values()):
                try:
                    self._delete_vm(vm_info)
                except Exception as e:
                    logger.error(f"Error deleting VM {vm_info.vm_name}: {e}")

        logger.info("VM pools shut down")
