class ContainerButton {
    constructor(containerId, containerName, buttonElement) {
        this.containerId = containerId;
        this.containerName = containerName;
        this.buttonElement = buttonElement;
        this.isPolling = false;
        this.pollInterval = null;
        
        this.init();
    }
    
    init() {
        // Start polling for status updates
        this.startPolling();
        
        // Add click handler
        this.buttonElement.addEventListener('click', (e) => this.handleClick(e));
    }
    
    async handleClick(e) {
        e.preventDefault();
        
        if (this.buttonElement.disabled) {
            return;
        }
        
        // Check current status before allowing navigation
        const status = await this.checkStatus();
        if (status && status.is_clickable) {
            // Open container session page
            window.location.href = `/session/${this.containerName}`;
        } else {
            // Show status message
            this.showStatusMessage(status);
        }
    }
    
    async checkStatus() {
        try {
            const response = await fetch(`/container/${this.containerId}/status`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error(`Error checking status for ${this.containerId}:`, error);
        }
        return null;
    }
    
    async updateButtonState() {
        const status = await this.checkStatus();
        if (status) {
            this.updateButton(status);
        }
    }
    
    updateButton(status) {
        const button = this.buttonElement;
        const iconElement = button.querySelector('.status-icon');
        const textElement = button.querySelector('.button-text');
        const statusElement = button.querySelector('.status-text');
        
        // Update button state based on container status
        if (status.is_clickable) {
            // Container is available and clickable
            button.disabled = false;
            button.className = 'container-button px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors duration-200 flex items-center space-x-2';
            iconElement.className = 'status-icon w-4 h-4 text-green-200';
            iconElement.setAttribute('data-lucide', 'play-circle');
            textElement.textContent = 'Connect';
            statusElement.textContent = `Status: ${status.container_status}`;
        } else if (status.is_locked) {
            // Container is locked by another user
            button.disabled = true;
            button.className = 'container-button px-4 py-2 bg-red-500 text-white rounded cursor-not-allowed opacity-75 flex items-center space-x-2';
            iconElement.className = 'status-icon w-4 h-4 text-red-200';
            iconElement.setAttribute('data-lucide', 'lock');
            textElement.textContent = 'In Use';
            statusElement.textContent = `Locked by: ${status.locked_by_ip}`;
        } else if (status.container_status === 'exited') {
            // Container is exited
            button.disabled = true;
            button.className = 'container-button px-4 py-2 bg-gray-500 text-white rounded cursor-not-allowed opacity-75 flex items-center space-x-2';
            iconElement.className = 'status-icon w-4 h-4 text-gray-200';
            iconElement.setAttribute('data-lucide', 'square');
            textElement.textContent = 'Stopped';
            statusElement.textContent = `Status: ${status.container_status}`;
        } else {
            // Container is in some other state (starting, etc.)
            button.disabled = true;
            button.className = 'container-button px-4 py-2 bg-yellow-500 text-white rounded cursor-not-allowed opacity-75 flex items-center space-x-2';
            iconElement.className = 'status-icon w-4 h-4 text-yellow-200';
            iconElement.setAttribute('data-lucide', 'loader');
            textElement.textContent = 'Loading...';
            statusElement.textContent = `Status: ${status.container_status}`;
        }
        
        // Re-create icons after updating data-lucide attributes
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }
    
    showStatusMessage(status) {
        if (!status) {
            alert('Unable to check container status. Please try again.');
            return;
        }
        
        if (status.is_locked) {
            alert(`Container is currently in use by ${status.locked_by_ip}`);
        } else if (status.container_status === 'exited') {
            alert('Container is stopped. Please wait for it to start.');
        } else {
            alert(`Container is not available. Status: ${status.container_status}`);
        }
    }
    
    startPolling() {
        if (this.isPolling) return;
        
        this.isPolling = true;
        // Update immediately
        this.updateButtonState();
        
        // Then poll every 5 seconds
        this.pollInterval = setInterval(() => {
            this.updateButtonState();
        }, 5000);
    }
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        this.isPolling = false;
    }
    
    destroy() {
        this.stopPolling();
        this.buttonElement.removeEventListener('click', this.handleClick);
    }
}

// Initialize all container buttons when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const containerButtons = document.querySelectorAll('.container-button');
    const buttonInstances = [];
    
    containerButtons.forEach(button => {
        const containerId = button.getAttribute('data-container-id');
        const containerName = button.getAttribute('data-container-name');
        
        if (containerId && containerName) {
            const instance = new ContainerButton(containerId, containerName, button);
            buttonInstances.push(instance);
        }
    });
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        buttonInstances.forEach(instance => instance.destroy());
    });
});