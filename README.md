# PyAirtable Automation Services

A consolidated microservice that combines file processing and workflow automation capabilities. This service consolidates the functionality of the previous File Processor and Workflow Engine services into a unified, efficient solution.

## Features

### File Processing
- **Multi-format Support**: PDF, DOC, DOCX, TXT, CSV, XLSX, XLS
- **Content Extraction**: Intelligent text extraction with metadata
- **File Management**: Upload, process, retrieve, and delete files
- **Validation**: File size limits and type validation
- **Status Tracking**: Real-time processing status monitoring

### Workflow Automation
- **CRUD Operations**: Create, read, update, delete workflows
- **Scheduling**: Cron-based workflow scheduling
- **Manual Triggers**: On-demand workflow execution
- **File Integration**: Workflows triggered by file uploads/processing
- **Execution History**: Complete audit trail of workflow runs
- **Step Types**: Log, File Process, Airtable Create/Update, Delay, Condition

### Integration Features
- **Backward Compatibility**: Maintains all original API endpoints
- **Cross-Service Triggers**: Files can trigger workflows automatically
- **Shared Background Processing**: Unified task management
- **Combined Health Checks**: Single monitoring endpoint

## Quick Start

### Prerequisites
- Python 3.11+
- Redis (optional, for caching)
- PostgreSQL or SQLite (for database)

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/pyairtable-automation-services.git
cd pyairtable-automation-services
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run the service**:
```bash
uvicorn main:app --host 0.0.0.0 --port 8006 --reload
```

### Docker Deployment

1. **Build and run with Docker**:
```bash
docker build -t pyairtable-automation-services .
docker run -p 8006:8006 -e DATABASE_URL=sqlite:///./data/app.db -v $(pwd)/data:/app/data pyairtable-automation-services
```

2. **Or use Docker Compose**:
```yaml
version: '3.8'
services:
  automation-services:
    build: .
    ports:
      - "8006:8006"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/automation
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./uploads:/app/uploads
      - ./data:/app/data
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: automation
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## API Documentation

### File Processing Endpoints

#### Upload File
```http
POST /files/upload
Content-Type: multipart/form-data

Form Data:
- file: [file to upload]
```

#### Get File Info
```http
GET /files/{file_id}
```

#### List Files
```http
GET /files?skip=0&limit=100&status=processed
```

#### Process File
```http
POST /files/process/{file_id}
```

#### Extract Content
```http
GET /files/extract/{file_id}
```

#### Delete File
```http
DELETE /files/{file_id}
```

### Workflow Management Endpoints

#### Create Workflow
```http
POST /workflows
Content-Type: application/json

{
  "name": "Process uploaded PDFs",
  "description": "Extract text from PDFs and create Airtable records",
  "config": {
    "steps": [
      {
        "type": "file_process",
        "name": "Extract PDF content"
      },
      {
        "type": "airtable_create",
        "name": "Create record",
        "table": "Documents",
        "fields": {
          "Name": "{filename}",
          "Content": "{content}",
          "File Size": "{file_size}"
        }
      }
    ]
  },
  "triggers": [
    {
      "type": "file_upload",
      "file_extensions": [".pdf"]
    }
  ],
  "cron_expression": "0 */6 * * *"
}
```

#### List Workflows
```http
GET /workflows?skip=0&limit=100&status=active
```

#### Get Workflow
```http
GET /workflows/{workflow_id}
```

#### Update Workflow
```http
PUT /workflows/{workflow_id}
Content-Type: application/json

{
  "name": "Updated workflow name",
  "is_enabled": false
}
```

#### Delete Workflow
```http
DELETE /workflows/{workflow_id}
```

#### Trigger Workflow
```http
POST /workflows/{workflow_id}/trigger
Content-Type: application/json

{
  "trigger_data": {
    "custom_param": "value"
  }
}
```

#### List Executions
```http
GET /workflows/executions?skip=0&limit=100&status=completed
```

#### Get Execution Details
```http
GET /workflows/executions/{execution_id}
```

### Health Check
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "pyairtable-automation-services",
  "components": {
    "database": "healthy",
    "scheduler": "healthy",
    "file_processor": "healthy",
    "workflow_engine": "healthy"
  },
  "version": "1.0.0"
}
```

## Workflow Configuration

### Step Types

#### 1. Log Step
```json
{
  "type": "log",
  "name": "Log message",
  "message": "Processing file {filename} with size {file_size}"
}
```

#### 2. File Process Step
```json
{
  "type": "file_process",
  "name": "Extract content",
  "file_id": "{triggered_file_id}"
}
```

#### 3. Airtable Create Step
```json
{
  "type": "airtable_create",
  "name": "Create record",
  "table": "Documents",
  "fields": {
    "Name": "{filename}",
    "Content": "{content}",
    "Upload Date": "{created_at}"
  }
}
```

#### 4. Airtable Update Step
```json
{
  "type": "airtable_update",
  "name": "Update record",
  "table": "Documents",
  "record_id": "recXXXXXX",
  "fields": {
    "Status": "Processed",
    "Updated": "{now}"
  }
}
```

#### 5. Delay Step
```json
{
  "type": "delay",
  "name": "Wait 30 seconds",
  "delay": 30
}
```

#### 6. Condition Step
```json
{
  "type": "condition",
  "name": "Check file size",
  "condition": {
    "type": "equals",
    "left": "{file_size}",
    "right": "1000000"
  }
}
```

### Trigger Types

#### File Upload Trigger
```json
{
  "type": "file_upload",
  "file_extensions": [".pdf", ".docx"],
  "max_file_size": 10485760,
  "mime_types": ["application/pdf"]
}
```

#### File Processed Trigger
```json
{
  "type": "file_processed",
  "file_extensions": [".csv"]
}
```

#### Scheduled Trigger (Cron)
```json
{
  "cron_expression": "0 9 * * 1-5"
}
```

### Template Variables

Variables available in workflow steps:
- `{workflow_id}` - Workflow ID
- `{execution_id}` - Execution ID
- `{filename}` - Original filename (if file trigger)
- `{file_id}` - File ID (if file trigger)
- `{file_size}` - File size in bytes
- `{content}` - Extracted file content
- `{created_at}` - ISO timestamp
- `{step_N_result}` - Result from step N

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8006` |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DATABASE_URL` | Database connection string | `sqlite:///./automation_services.db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `UPLOAD_DIRECTORY` | File upload directory | `./uploads` |
| `MAX_FILE_SIZE` | Maximum file size (bytes) | `104857600` (100MB) |
| `ALLOWED_EXTENSIONS` | Allowed file extensions | `.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls` |
| `AIRTABLE_API_KEY` | Airtable API key | `` |
| `AIRTABLE_BASE_ID` | Airtable base ID | `` |

### File Size Limits
- Default: 100MB per file
- Configurable via `MAX_FILE_SIZE` environment variable
- Validation occurs during upload

### Supported File Types
- **PDF**: Text extraction with page metadata
- **DOC/DOCX**: Paragraphs and tables
- **TXT**: Multi-encoding support
- **CSV**: Automatic delimiter detection
- **XLSX/XLS**: Multiple sheets support

## Monitoring and Logging

### Health Checks
- **Endpoint**: `GET /health`
- **Components**: Database, Scheduler, File Processor, Workflow Engine
- **Interval**: Configurable (default: 30s)

### Logging
- **Format**: Structured JSON logging
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Components**: Request/response, workflow execution, file processing

### Metrics
- File processing statistics
- Workflow execution metrics
- System health indicators

## Development

### Project Structure
```
pyairtable-automation-services/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── database.py            # Database models and connections
├── routes/
│   ├── files.py           # File processing endpoints
│   └── workflows.py       # Workflow management endpoints
├── services/
│   ├── file_service.py    # File processing logic
│   ├── workflow_service.py # Workflow execution logic
│   └── scheduler.py       # Cron-based scheduling
├── utils/
│   └── file_utils.py      # File content extraction
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── .env.example          # Environment configuration template
└── README.md             # This file
```

### Running Tests
```bash
pip install pytest pytest-asyncio
pytest
```

### Code Formatting
```bash
pip install black isort flake8
black .
isort .
flake8 .
```

## Deployment

### Production Considerations
1. **Database**: Use PostgreSQL for production
2. **Redis**: Configure for caching and background tasks
3. **File Storage**: Consider external storage (S3, etc.)
4. **Security**: Set strong `SECRET_KEY` and configure CORS
5. **Monitoring**: Enable metrics and health checks
6. **Scaling**: Use multiple workers with load balancer

### Docker Production
```bash
docker build --target production -t pyairtable-automation-services:prod .
docker run -d -p 8006:8006 --name automation-services \
  -e DATABASE_URL=postgresql://user:pass@db:5432/automation \
  -e REDIS_URL=redis://redis:6379/0 \
  -e WORKERS=4 \
  pyairtable-automation-services:prod
```

## Migration from Separate Services

This service consolidates the File Processor (port 8005) and Workflow Engine (port 8007) into a single service (port 8006).

### Backward Compatibility
- All original endpoints are maintained
- Legacy routes are supported (marked as deprecated)
- Database migration scripts available
- Configuration mapping provided

### Migration Steps
1. Stop existing services
2. Backup databases
3. Deploy consolidated service
4. Update client configurations to use port 8006
5. Verify functionality
6. Remove old services

## API Rate Limiting

Default limits:
- File uploads: 10 per minute
- Workflow triggers: 30 per minute
- General API: 100 per minute

## Security

### Authentication
- JWT token support (optional)
- API key authentication
- CORS configuration

### File Security
- File type validation
- Size limits enforced
- Virus scanning (configurable)
- Secure file storage

## Troubleshooting

### Common Issues

1. **File Upload Fails**
   - Check file size limits
   - Verify file type is allowed
   - Ensure upload directory exists and is writable

2. **Workflow Not Executing**
   - Verify workflow is active and enabled
   - Check cron expression syntax
   - Review scheduler logs

3. **Database Connection Issues**
   - Verify DATABASE_URL format
   - Check database server status
   - Review connection pool settings

4. **Redis Connection Problems**
   - Verify REDIS_URL format
   - Check Redis server status
   - Review Redis authentication

### Logs Location
- Application logs: stdout/stderr
- File processing logs: `logs/file_processing.log`
- Workflow execution logs: `logs/workflow_execution.log`

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation
3. Check application logs
4. Open a GitHub issue

## License

MIT License - see LICENSE file for details.