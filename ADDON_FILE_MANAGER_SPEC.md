# Custom Addon File Manager - Technical Specification

## Purpose
A file manager system for custom Odoo addons that can be uploaded, stored, and deployed to VPS servers.

## Architecture Overview

### 1. **File Upload & Storage**
- Upload custom addon files (Python, XML, JS, CSS, images)
- Store files in organized directory structure
- Support multiple file types and compressed folders
- File versioning and metadata tracking

### 2. **File Management**
- List all uploaded addons with metadata
- Download individual addons or bundles
- Delete unused addons
- File browser interface (future enhancement)

### 3. **VPS Deployment**
- Deploy addons to selected VPS servers
- Create custom-addons directory structure on VPS
- Mount volumes for Odoo containers
- Execute deployment commands like:
  ```bash
  # Create addon directory on VPS
  mkdir -p ~/odoo/custom-addons/addon_name

  # Copy addon files to VPS
  scp -r addon_files/* vps_host:~/odoo/custom-addons/addon_name/

  # Deploy with Docker volume mount
  docker run -v ~/odoo/custom-addons:/mnt/extra-addons \
    -p 8069:8069 --name odoo \
    -t odoo:17.0
  ```

## Required Backend APIs

### 1. **File Upload API**
```
POST /api/v1/addons/upload
Content-Type: multipart/form-data

Form Fields:
- name: string (addon name)
- description: string (optional)
- addon_files: File[] (multiple files)
```

### 2. **List Addons API**
```
GET /api/v1/addons
Response: {
  addons: [{
    id: string,
    name: string,
    description: string,
    file_count: number,
    total_size_mb: number,
    file_types: string[],
    uploaded_at: string,
    last_deployed: string
  }]
}
```

### 3. **Deploy to VPS API**
```
POST /api/v1/addons/{addon_id}/deploy
Body: {
  vps_id: string,
  deployment_path: string (optional, default: ~/odoo/custom-addons)
}
```

### 4. **File Download API**
```
GET /api/v1/addons/{addon_id}/download
Response: ZIP file containing all addon files
```

### 5. **Delete Addon API**
```
DELETE /api/v1/addons/{addon_id}
```

## File Storage Structure
```
/addon_storage/
├── addon_1/
│   ├── metadata.json
│   ├── __manifest__.py
│   ├── models/
│   ├── views/
│   ├── static/
│   └── data/
├── addon_2/
└── ...
```

## Frontend Features

### Current Implementation:
- ✅ Upload form for addon files
- ✅ File type validation
- ✅ Multiple file support
- ✅ Preview messages for future functionality
- ✅ Deploy to VPS button (placeholder)

### Next Phase:
- File browser interface
- VPS selection for deployment
- Deployment progress tracking
- Addon dependency management
- File editing capabilities (advanced)

## VPS Integration
The addon deployment will integrate with existing VPS management to:
1. Select target VPS from available hosts
2. Execute deployment commands via SSH
3. Monitor deployment status
4. Manage addon lifecycle on VPS

## Use Cases

1. **Developer Workflow:**
   - Upload custom addon ZIP file
   - Deploy to development VPS
   - Test addon functionality
   - Deploy to production VPS

2. **File Management:**
   - Browse uploaded addons
   - Download addon backups
   - Clean up unused addons

3. **Multi-VPS Deployment:**
   - Deploy same addon to multiple VPS servers
   - Manage addon versions across environments
   - Track deployment history