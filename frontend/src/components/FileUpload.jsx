import React, { useRef } from 'react'
import { Paperclip } from 'lucide-react'

const FileUpload = ({ onFilesSelected, disabled, customButton }) => {
  const fileInputRef = useRef(null)

  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || [])
    const validFiles = files.filter(file => {
      const validTypes = [
        'application/pdf',
        'text/markdown',
        'text/x-markdown',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // docx
        'application/msword', // doc
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/vnd.ms-powerpoint'
      ]
      const validExtensions = ['.pdf', '.md', '.markdown', '.doc', '.docx', '.ppt', '.pptx']
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
      
      return validTypes.includes(file.type) || 
             validExtensions.includes(fileExtension)
    })

    if (validFiles.length > 0) {
      onFilesSelected(validFiles)
    } else {
      alert('Please upload PDF, DOC, DOCX, or Markdown files')
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <>
      {customButton ? (
        customButton(handleFileSelect)
      ) : (
        <button
          type="button"
          onClick={handleFileSelect}
          disabled={disabled}
          className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          title="Attach files (PDF, DOC, DOCX, MD)"
        >
          <Paperclip className="w-5 h-5" />
        </button>
      )}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.md,.markdown,.doc,.docx,.ppt,.pptx"
        onChange={handleFileChange}
        className="hidden"
      />
    </>
  )
}

export default FileUpload
