'use client';

import { FileUpload } from '@/components/shared/file-upload';
import { H1, H2, Body } from '@/components/ui/typography';
import { useAppStore } from '@/lib/stores/app.store';

export default function FileUploadDemoPage() {
  const { addNotification } = useAppStore();

  // Suppress TypeScript unused variable warning
  void addNotification;

  const handleFileUpload = async (_files: File[]) => {
    // Simulate API upload
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // In real implementation, you would upload to your API here
    // const formData = new FormData()
    // files.forEach(file => formData.append('files', file))
    // await apiClient.post('/upload', formData)
  };

  const handleSingleFileUpload = async (_files: File[]) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
  };

  const handleImageUpload = async (_files: File[]) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
  };

  return (
    <div className="container mx-auto space-y-12 p-8">
      <div className="space-y-4">
        <H1>File Upload Component Demo</H1>
        <Body color="muted">
          Drag and drop file upload component with progress tracking and validation.
        </Body>
      </div>

      {/* Default Multi-File Upload */}
      <section className="space-y-4">
        <H2>Default Multi-File Upload</H2>
        <Body>Accepts multiple files of various types with 10MB size limit.</Body>
        <FileUpload onUpload={handleFileUpload} className="max-w-2xl" />
      </section>

      {/* Single File Upload */}
      <section className="space-y-4">
        <H2>Single File Upload</H2>
        <Body>Accepts only one file at a time.</Body>
        <FileUpload onUpload={handleSingleFileUpload} multiple={false} className="max-w-2xl" />
      </section>

      {/* Image Only Upload */}
      <section className="space-y-4">
        <H2>Image Only Upload</H2>
        <Body>Accepts only image files (PNG, JPG, JPEG) with 5MB limit.</Body>
        <FileUpload
          onUpload={handleImageUpload}
          acceptedTypes={['png', 'jpg', 'jpeg']}
          maxSize={5 * 1024 * 1024}
          className="max-w-2xl"
        />
      </section>

      {/* Document Upload */}
      <section className="space-y-4">
        <H2>Document Upload</H2>
        <Body>Accepts only document files (PDF, DOC, DOCX).</Body>
        <FileUpload
          onUpload={handleFileUpload}
          acceptedTypes={['pdf', 'doc', 'docx']}
          maxFiles={3}
          className="max-w-2xl"
        />
      </section>

      {/* No File List */}
      <section className="space-y-4">
        <H2>Upload Without File List</H2>
        <Body>File list display is hidden.</Body>
        <FileUpload onUpload={handleFileUpload} showFileList={false} className="max-w-2xl" />
      </section>

      {/* Disabled State */}
      <section className="space-y-4">
        <H2>Disabled State</H2>
        <Body>Upload is disabled.</Body>
        <FileUpload onUpload={handleFileUpload} disabled className="max-w-2xl" />
      </section>
    </div>
  );
}
