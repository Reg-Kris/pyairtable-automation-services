# Automation Services - Claude Context

## 🎯 Service Purpose
This is the **automation and file processing engine** of the PyAirtable ecosystem - a consolidated microservice that combines file processing and workflow automation capabilities. It handles multi-format file processing, content extraction, and complex workflow automation with scheduling and triggers.

## 🏗️ Current State

### Deployment Status
- **Environment**: ✅ Local Kubernetes (Minikube)
- **Services Running**: ✅ 7 out of 9 services operational
- **Database Analysis**: ✅ Airtable test database analyzed (34 tables, 539 fields)
- **Metadata Tool**: ✅ Table analysis tool executed successfully

### Service Status
- **File Processing**: ✅ Multi-format support (PDF, DOC, DOCX, TXT, CSV, XLSX, XLS)
- **Content Extraction**: ✅ Intelligent text extraction with metadata
- **Workflow Engine**: ✅ CRUD operations with cron-based scheduling
- **File Management**: ✅ Upload, process, retrieve, and delete operations
- **Background Processing**: ✅ Unified task management
- **Cross-Service Integration**: ✅ Files can trigger workflows automatically
- **Database**: ✅ PostgreSQL with SQLAlchemy ORM
- **Caching**: ✅ Redis for background task management

### Recent Fixes Applied
- ✅ Pydantic v2 compatibility issues resolved
- ✅ Gemini ThinkingConfig configuration fixed
- ✅ SQLAlchemy metadata handling updated
- ✅ Service deployment to Kubernetes completed

## 🔧 Technical Details
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for background tasks
- **File Processing**: Multi-format content extraction
- **Scheduling**: Cron-based with APScheduler
- **Python**: 3.11+
- **Port**: 8006

## 📋 API Endpoints

### File Processing Routes (/files/*)
```python
POST   /files/upload                    # Upload file for processing
GET    /files/{file_id}                # Get file info and status
GET    /files                          # List files with filtering
POST   /files/process/{file_id}        # Process uploaded file
GET    /files/extract/{file_id}        # Extract content from file
DELETE /files/{file_id}                # Delete file and data
```

### Workflow Management Routes (/workflows/*)
```python
POST   /workflows                      # Create new workflow
GET    /workflows                      # List workflows with filtering
GET    /workflows/{workflow_id}        # Get workflow details
PUT    /workflows/{workflow_id}        # Update workflow configuration
DELETE /workflows/{workflow_id}        # Delete workflow
POST   /workflows/{workflow_id}/trigger # Manually trigger workflow
GET    /workflows/executions           # List workflow executions
GET    /workflows/executions/{exec_id} # Get execution details
```

### System Routes
```python
GET    /health                         # Health check with component status
```

## 🛠️ File Processing Features

### Supported File Types
- **PDF**: Text extraction with page metadata
- **DOC/DOCX**: Paragraphs and tables extraction
- **TXT**: Multi-encoding support
- **CSV**: Automatic delimiter detection
- **XLSX/XLS**: Multiple sheets support

### Processing Pipeline
```python
File Upload → Validation → Content Extraction → Metadata Creation → Trigger Check
     ↓             ↓              ↓                   ↓               ↓
Size/Type      Store File    Extract Text      Store Metadata   Workflow Trigger
```

## 🔄 Workflow Automation Features

### Step Types Available
1. **Log Step**: Custom logging with template variables
2. **File Process Step**: Extract content from uploaded files
3. **Airtable Create Step**: Create records in Airtable tables
4. **Airtable Update Step**: Update existing records
5. **Delay Step**: Add time delays between steps
6. **Condition Step**: Conditional execution logic

### Trigger Types
- **File Upload**: Triggered when specific file types are uploaded
- **File Processed**: Triggered after file processing completes
- **Scheduled**: Cron-based scheduling for recurring workflows

### Template Variables
- `{workflow_id}`, `{execution_id}` - Workflow identifiers
- `{filename}`, `{file_id}`, `{file_size}` - File-related data
- `{content}` - Extracted file content
- `{created_at}` - Timestamp information
- `{step_N_result}` - Results from previous steps

## 🚀 Immediate Priorities

1. **Enhanced Error Handling** (HIGH)
   ```python
   # Improve error recovery for failed workflow steps
   # Add retry mechanisms for transient failures
   # Better error reporting and logging
   ```

2. **Performance Optimization** (HIGH)
   ```python
   # Optimize file processing for large files
   # Implement streaming for file uploads
   # Add file processing caching
   ```

3. **Comprehensive Testing** (MEDIUM)
   ```python
   # Unit tests for all file processing formats
   # Integration tests for workflow execution
   # Load tests for concurrent file processing
   ```

## 🔮 Future Enhancements

### Phase 1 (Next Sprint)
- [ ] Enhanced file validation and virus scanning
- [ ] Workflow step templates and reusable components
- [ ] Real-time workflow execution monitoring
- [ ] File processing progress tracking

### Phase 2 (Next Month)
- [ ] Advanced workflow conditions and logic
- [ ] External service integrations (email, webhooks)
- [ ] Bulk file processing capabilities
- [ ] Workflow versioning and rollback

### Phase 3 (Future)
- [ ] Visual workflow builder interface
- [ ] Machine learning-powered content analysis
- [ ] Advanced file format support
- [ ] Distributed file processing

## ⚠️ Known Issues
1. **File size limits** - Currently 100MB max, could be increased
2. **Limited workflow debugging** - Need better execution visibility
3. **No workflow pause/resume** - Workflows run to completion or fail
4. **Basic file security** - Could add virus scanning and content filtering

## 🧪 Testing Strategy
```python
# Priority test coverage:
- File upload and processing for all supported formats
- Workflow creation and execution end-to-end
- Trigger mechanism testing (file upload, scheduling)
- Error handling and recovery scenarios
- Performance testing for large files and complex workflows
```

## 📊 Performance Targets
- **File Upload**: < 5s for files up to 100MB
- **Content Extraction**: < 10s for standard documents
- **Workflow Execution**: < 2s per step (excluding delays)
- **Concurrent Files**: 50+ simultaneous processing
- **Memory Usage**: < 500MB per worker

## 🤝 Service Dependencies
```
Frontend → API Gateway → Automation Services → Airtable Gateway
                              ↓                      ↓
                         PostgreSQL            Airtable API
                              ↓
                            Redis
```

## 💡 Development Tips
1. Use template variables for dynamic workflow content
2. Test file processing with various file sizes and formats
3. Monitor Redis for background task queues
4. Use cron expressions for precise scheduling

## 🚨 Critical Configuration
```python
# Required environment variables:
DATABASE_URL=postgresql://...          # Database connection
REDIS_URL=redis://redis:6379          # Background task queue
UPLOAD_DIRECTORY=./uploads            # File storage location
MAX_FILE_SIZE=104857600              # 100MB file size limit
AIRTABLE_API_KEY=your_key            # For Airtable integrations
```

## 🔒 Security Considerations
- **File Validation**: Type and size limits enforced
- **Secure Storage**: Files stored with restricted access
- **Content Sanitization**: Extracted content is sanitized
- **Workflow Isolation**: Each execution runs in isolation
- **API Authentication**: JWT and API key support

## 📈 Monitoring Metrics
```python
# Key metrics to track:
automation_files_uploaded_total{type}          # File upload counts
automation_files_processed_duration_seconds    # Processing time
automation_workflows_executed_total{status}    # Workflow execution
automation_workflow_step_duration_seconds      # Step performance
automation_file_storage_bytes_total           # Storage usage
```

## 🎯 Consolidation Benefits

### Before vs After
- **Before**: File Processor (port 8005) + Workflow Engine (port 8007)
- **After**: Unified Automation Services (port 8006)

### Integration Benefits
- Cross-service triggers: Files automatically trigger workflows
- Shared background processing with unified task management
- Combined health checks and monitoring
- Reduced inter-service communication overhead

### Resource Efficiency
- 50% reduction in container overhead
- Shared database connections and Redis client
- Unified configuration and logging
- Single deployment and monitoring point

## 🔄 Service Communication
```python
# File processing flow:
Client → API Gateway → Automation Services → File Storage
                             ↓
                        PostgreSQL (metadata)

# Workflow execution flow:
Scheduler → Workflow Engine → Step Execution → Airtable Gateway
                    ↓               ↓               ↓
               PostgreSQL      Redis Queue    External APIs
```

Remember: This service is the **automation backbone** of PyAirtable - enabling intelligent file processing and complex workflow orchestration that bridges file content with Airtable operations!