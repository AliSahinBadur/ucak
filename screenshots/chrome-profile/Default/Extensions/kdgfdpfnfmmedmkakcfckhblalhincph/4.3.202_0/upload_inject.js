(() => {
    const dragAndDrop = function () {
        const originalWebkitGetAsEntry = DataTransferItem.prototype.webkitGetAsEntry;
        const originalGetAsFileSystemHandle = DataTransferItem.prototype.getAsFileSystemHandle;

        DataTransferItem.prototype.getAsFileSystemHandle = async function () {
            let handle;

            if (typeof originalGetAsFileSystemHandle === 'function') {
                handle = await originalGetAsFileSystemHandle.call(this);
            }

            if (handle === undefined) {
                const file = this.getAsFile();

                if (!file) return handle;

                const fallbackHandle = {
                    kind: 'file',
                    name: file.name,
                    getFile: async () => file,
                    isSameEntry: async function (other) {
                        if (!other) return false;

                        // More comprehensive type checking
                        if (other.kind !== 'file' || typeof other.name !== 'string' || other.name !== file.name) {
                            return false;
                        }

                        try {
                            let otherFile;

                            if (typeof other.getFile === 'function') {
                                otherFile = await other.getFile();
                            } else if (other instanceof File) {
                                otherFile = other;
                            } else {
                                return false;
                            }

                            if (!(otherFile instanceof File)) {
                                return false;
                            }

                            // Basic property comparison
                            if (file.size !== otherFile.size || file.lastModified !== otherFile.lastModified) {
                                return false;
                            }

                            // Optional: Additional checks for more confidence
                            // Note: These might be overkill depending on your use case

                            // Check file type if available
                            if (file.type !== otherFile.type) {
                                return false;
                            }

                            return true;
                        } catch (error) {
                            return false;
                        }
                    },
                    createWritable: async function () {
                        throw new Error('Cannot create writable stream: file was obtained via drop operation, not File System Access API');
                    },
                };

                if (window.FileSystemFileHandle && window.FileSystemFileHandle.prototype) {
                    Object.setPrototypeOf(fallbackHandle, window.FileSystemFileHandle.prototype);
                }

                return fallbackHandle;
            } else {
                return handle;
            }
        };

        //webkitGetAsEntry function returns null if we copy dataTransfer files/items to another datatransfer object
        DataTransferItem.prototype.webkitGetAsEntry = function () {
            const entry = originalWebkitGetAsEntry.call(this);
            const file = this.getAsFile();
            if (entry === null && file !== null) {
                file.isDirectory = false;
                file.fullPath = file.name;
                file.isFile = true;
                file.file = function (cb) {
                    cb(file);
                };
                return file;
            } else {
                return originalWebkitGetAsEntry.call(this);
            }
        };

        // Needed for outlook web drop position issue
        window.addEventListener(
            'drop',
            e => {
                if (e.isTrusted || e.detail !== -2) return;
                // -2 To identify dx synthetic events in page scripts

                e.stopImmediatePropagation();

                const scrollX = window.scrollX || document.documentElement.scrollLeft;
                const scrollY = window.scrollY || document.documentElement.scrollTop;

                const event = new DragEvent('drop', {
                    bubbles: true,
                    cancelable: true,
                    clientX: e.clientX,
                    clientY: e.clientY,
                    dataTransfer: e.dataTransfer,
                });

                Object.defineProperty(event, 'pageX', { value: e.clientX + scrollX });
                Object.defineProperty(event, 'pageY', { value: e.clientY + scrollY });
                e.target.dispatchEvent(event);
            },
            true
        );
    };

    const fileSystemHandle = function () {
        const originalFn = window.showOpenFilePicker;

        function messageWait(msgObject) {
            return new Promise(resolve => {
                const messageHandler = e => {
                    const { message, payload } = e.data;
                    if (message === msgObject.message + '_RESPONSE') {
                        window.removeEventListener('message', messageHandler);
                        resolve(payload);
                    }
                };
                window.addEventListener('message', messageHandler);
                window.postMessage(msgObject);
            });
        }

        window.showOpenFilePicker = async function (options) {
            let fileHandleResponse;

            const { openFilePicker, fileTransferCheckResponse } = await messageWait({ message: 'DX_FILE_PICKER_ALLOWED' });

            if (!openFilePicker) return [];

            if (fileTransferCheckResponse.active === false || !fileTransferCheckResponse.policy) {
                window.showOpenFilePicker = originalFn;
                return window.showOpenFilePicker(options);
            }

            fileHandleResponse = await originalFn(options);

            if (fileTransferCheckResponse.policy?.mimeCheck) {
                const { mimeConfig } = await messageWait({
                    message: 'DX_FILE_PICKER_PERFORM_MIME_CHECK',
                    payload: {
                        fileHandleResponse,
                    },
                });

                fileHandleResponse = fileHandleResponse.filter((fileHandle, index) => {
                    return mimeConfig[index].allowed;
                });

                return fileHandleResponse;
            } else {
                window.postMessage({
                    message: 'DX_FILE_PICKER_CREATE_UPLOAD_ALLOWED_LOG',
                    payload: {
                        fileHandleResponse,
                    },
                });
                return fileHandleResponse;
            }
        };
    };

    dragAndDrop();
    fileSystemHandle();
})();
