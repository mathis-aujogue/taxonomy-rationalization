"""FastAPI main application."""

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
from typing import Optional

from .database import get_db, init_db, MatchSession
from .models import (
    UploadRequest,
    IngestRequest,
    AugmentRequest,
    MatchRequest,
    MatchResponse,
    JobListResponse,
    JobInfo,
    TaxonomyResponse,
    TaxonomyNode,
    ExportRequest,
    ColumnMapping,
    MatchSessionCreate,
    MatchSessionUpdate,
    MatchSessionResponse,
    ExportMatchResultsRequest,
    ExportTaxonomyRequest,
    ExportVectorStatusRequest,
)
from .services import TaxonomyService
from .vector_status import check_vector_embeddings_status
from contextlib import asynccontextmanager
from lib.services import TaxonomyServices
from utils.config.constants import constants


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    init_db()
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="Taxonomy Rationalization API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Taxonomy Rationalization API"}


@app.post("/upload")
async def upload_taxonomy(
    file: UploadFile = File(...),
    target_id: Optional[str] = Form(None),
    l1_column: Optional[str] = Form(None),
    l2_column: Optional[str] = Form(None),
    l3_column: Optional[str] = Form(None),
    definition_column: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a taxonomy CSV file."""
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id is required")
    if not l3_column:
        raise HTTPException(status_code=400, detail="l3_column is required")

    # Read file content
    content = await file.read()

    # Parse CSV to get headers
    df = pd.read_csv(io.BytesIO(content), nrows=0)
    available_columns = list(df.columns)

    # Validate columns exist
    if l3_column not in available_columns:
        raise HTTPException(
            status_code=400, detail=f"Column '{l3_column}' not found in CSV. Available: {available_columns}"
        )

    column_mapping = ColumnMapping(
        l1=l1_column if l1_column in available_columns else None,
        l2=l2_column if l2_column in available_columns else None,
        l3=l3_column,
        definition=definition_column if definition_column in available_columns else None,
    )

    service = TaxonomyService(db)
    job = await service.upload_taxonomy(target_id, file.filename, content, column_mapping)

    return {
        "target_id": job.target_id,
        "filename": job.filename,
        "status": job.status,
        "column_mapping": job.column_mapping,
    }


@app.post("/ingest")
async def ingest_taxonomy(request: IngestRequest, db: Session = Depends(get_db)):
    """Ingest taxonomy embeddings into vector database."""
    service = TaxonomyService(db)
    try:
        job = await service.ingest_taxonomy(request.target_id, request.clear_existing)
        result = getattr(job, "_ingestion_result", None) or {}
        l3_count = result.get("l3_count", 0)
        total_embeddings = result.get("total_embeddings", 0)
        return {
            "target_id": job.target_id,
            "status": job.status,
            "message": "Ingestion completed successfully",
            "l3_count": l3_count,
            "total_embeddings": total_embeddings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/augment")
async def augment_taxonomy(request: AugmentRequest, db: Session = Depends(get_db)):
    """Generate LLM descriptions for taxonomy."""
    service = TaxonomyService(db)
    try:
        job = await service.augment_taxonomy(
            request.target_id, request.prompt_template, request.llm_model
        )
        return {
            "target_id": job.target_id,
            "status": job.status,
            "message": "Augmentation completed successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/match", response_model=MatchResponse)
async def match_taxonomy(request: MatchRequest, db: Session = Depends(get_db)):
    """Run hybrid matching."""
    service = TaxonomyService(db)
    try:
        results = await service.match_taxonomy(
            request.our_target_id,
            request.client_target_id,
            request.threshold,
            request.weights,
            request.limit,
        )

        total = len(results)
        matched = sum(1 for r in results if r.matched_l3)
        unmatched = total - matched
        avg_confidence = (
            sum(r.confidence for r in results if r.matched_l3) / matched if matched > 0 else 0.0
        )

        return MatchResponse(
            results=results,
            total=total,
            matched=matched,
            unmatched=unmatched,
            average_confidence=round(avg_confidence, 3),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(db: Session = Depends(get_db)):
    """List all taxonomy jobs."""
    service = TaxonomyService(db)
    jobs = service.get_jobs()

    return JobListResponse(
        jobs=[
            JobInfo(
                id=job.id,
                target_id=job.target_id,
                filename=job.filename,
                status=job.status,
                column_mapping=ColumnMapping(**job.column_mapping),
                created_at=job.created_at,
                updated_at=job.updated_at,
                error_message=job.error_message,
            )
            for job in jobs
        ]
    )


@app.get("/jobs/{target_id}", response_model=JobInfo)
async def get_job(target_id: str, db: Session = Depends(get_db)):
    """Get a specific job by target_id."""
    service = TaxonomyService(db)
    job = service.get_job(target_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobInfo(
        id=job.id,
        target_id=job.target_id,
        filename=job.filename,
        status=job.status,
        column_mapping=ColumnMapping(**job.column_mapping),
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
    )


@app.get("/our-taxonomy/{target_id}", response_model=TaxonomyResponse)
async def get_our_taxonomy(target_id: str, db: Session = Depends(get_db)):
    """Get our taxonomy for visualization."""
    service = TaxonomyService(db)
    try:
        nodes_data = await service.get_our_taxonomy(target_id)

        # Build tree structure
        nodes_map = {}
        root_nodes = []

        for node_data in nodes_data:
            l1 = node_data.get("l1", "")
            l2 = node_data.get("l2", "")
            l3 = node_data.get("l3", "")

            # Create node
            node = TaxonomyNode(
                l1=l1 if l1 else None,
                l2=l2 if l2 else None,
                l3=l3,
                definition=node_data.get("definition"),
                children=[],
            )

            # Build hierarchy
            if l1 and l2:
                key = f"{l1}::{l2}"
                if key not in nodes_map:
                    parent = TaxonomyNode(l1=l1, l2=l2, l3="", children=[])
                    nodes_map[key] = parent
                    if l1 not in nodes_map:
                        l1_node = TaxonomyNode(l1=l1, l2="", l3="", children=[])
                        nodes_map[l1] = l1_node
                        root_nodes.append(l1_node)
                    nodes_map[l1].children.append(parent)
                nodes_map[key].children.append(node)
            elif l2:
                key = l2
                if key not in nodes_map:
                    parent = TaxonomyNode(l2=l2, l3="", children=[])
                    nodes_map[key] = parent
                    root_nodes.append(parent)
                nodes_map[key].children.append(node)
            else:
                root_nodes.append(node)

        return TaxonomyResponse(target_id=target_id, nodes=root_nodes)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vector-status")
async def get_vector_status(target_id: Optional[str] = None):
    """Get status of vector embeddings in the database."""
    try:
        status = await check_vector_embeddings_status(target_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/target-ids")
async def get_target_ids():
    """Get list of available target IDs from vector database."""
    services = TaxonomyServices()
    await services.post_init()
    
    try:
        table_name = constants.TAXONOMY_EMBEDDINGS_TABLE_NAME
        
        # Get table structure
        structure_query = f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position;
        """
        
        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(structure_query)
                columns = cur.fetchall()
        
        column_names = [col[0] for col in columns]
        has_target_id_column = "target_id" in column_names
        
        # Find metadata column
        metadata_col = None
        for col_name, col_type in columns:
            if "metadata" in col_name.lower():
                metadata_col = col_name
                break
        
        if not metadata_col:
            return {"target_ids": []}
        
        # Query distinct target_ids
        if has_target_id_column:
            query = f"""
            SELECT DISTINCT target_id
            FROM {table_name}
            WHERE target_id IS NOT NULL
            ORDER BY target_id;
            """
        else:
            query = f"""
            SELECT DISTINCT ({metadata_col}->>'target_id') as target_id
            FROM {table_name}
            WHERE {metadata_col}->>'target_id' IS NOT NULL
            ORDER BY target_id;
            """
        
        with services.connection_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
        
        target_ids = [row[0] for row in rows if row[0]]
        
        # Only include targets with complete records (ready for hybrid matching)
        result = []
        for target_id in target_ids:
            status = await check_vector_embeddings_status(target_id)
            target_status = status.get("targets", {}).get(target_id, {})
            ready_for_hybrid_matching = target_status.get("ready_for_hybrid_matching", False)
            if ready_for_hybrid_matching:
                result.append({
                    "target_id": target_id,
                    "ready_for_hybrid_matching": ready_for_hybrid_matching,
                    "num_categories": target_status.get("num_categories", 0),
                })
        
        return {"target_ids": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        await services.aclose()


@app.post("/export")
async def export_taxonomy(request: ExportRequest, db: Session = Depends(get_db)):
    """Export matched taxonomy to CSV or Excel."""
    service = TaxonomyService(db)
    job = service.get_job(request.target_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get match results (would need to be stored or regenerated)
    # For now, return the original file
    file_path = service.upload_dir / f"{request.target_id}_{job.filename}"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if request.format == "excel":
        # Convert to Excel
        df = pd.read_csv(file_path)
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{request.target_id}.xlsx"'},
        )
    else:
        return FileResponse(
            file_path, media_type="text/csv", filename=f"{request.target_id}.csv"
        )


@app.post("/match-sessions", response_model=MatchSessionResponse)
async def create_match_session(request: MatchSessionCreate, db: Session = Depends(get_db)):
    """Create a new match session."""
    session = MatchSession(
        our_target_id=request.our_target_id,
        client_target_id=request.client_target_id,
        threshold=str(request.threshold) if request.threshold else None,
        results=[r.model_dump() for r in request.results],
        validation_states={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return MatchSessionResponse(
        id=session.id,
        our_target_id=session.our_target_id,
        client_target_id=session.client_target_id,
        threshold=float(session.threshold) if session.threshold else None,
        results=[MatchResult(**r) for r in session.results],
        validation_states=session.validation_states,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.get("/match-sessions/{session_id}", response_model=MatchSessionResponse)
async def get_match_session(session_id: int, db: Session = Depends(get_db)):
    """Get a match session by ID."""
    session = db.query(MatchSession).filter(MatchSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Match session not found")
    
    return MatchSessionResponse(
        id=session.id,
        our_target_id=session.our_target_id,
        client_target_id=session.client_target_id,
        threshold=float(session.threshold) if session.threshold else None,
        results=[MatchResult(**r) for r in session.results],
        validation_states=session.validation_states,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.patch("/match-sessions/{session_id}", response_model=MatchSessionResponse)
async def update_match_session(
    session_id: int, 
    request: MatchSessionUpdate,
    db: Session = Depends(get_db)
):
    """Update validation state for a match session."""
    session = db.query(MatchSession).filter(MatchSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Match session not found")
    
    session.validation_states = request.validation_states
    db.commit()
    db.refresh(session)
    
    return MatchSessionResponse(
        id=session.id,
        our_target_id=session.our_target_id,
        client_target_id=session.client_target_id,
        threshold=float(session.threshold) if session.threshold else None,
        results=[MatchResult(**r) for r in session.results],
        validation_states=session.validation_states,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@app.get("/match-sessions/{session_id}/export")
async def export_match_session(session_id: int, db: Session = Depends(get_db)):
    """Export validated match session results to CSV."""
    session = db.query(MatchSession).filter(MatchSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Match session not found")
    
    # Filter to only validated results
    validated_results = [
        MatchResult(**r) for r in session.results
        if session.validation_states.get(r.get('target_l3', ''), '') == 'validated'
    ]
    
    if not validated_results:
        raise HTTPException(status_code=400, detail="No validated results to export")
    
    # Convert to DataFrame
    rows = []
    for result in validated_results:
        rows.append({
            'target_l1': result.target_l1,
            'target_l2': result.target_l2,
            'target_l3': result.target_l3,
            'matched_l1': result.matched_l1,
            'matched_l2': result.matched_l2,
            'matched_l3': result.matched_l3,
            'confidence': result.confidence,
        })
    
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.read()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="match_session_{session_id}.csv"'},
    )


@app.post("/export/match-results")
async def export_match_results(request: ExportMatchResultsRequest):
    """Export match results to CSV or Excel."""
    if not request.results:
        raise HTTPException(status_code=400, detail="No results to export")
    
    # Convert to DataFrame
    rows = []
    for result in request.results:
        validation_status = 'pending'
        if request.validation_states:
            validation_status = request.validation_states.get(result.target_l3, 'pending')
        
        rows.append({
            'Client L1': result.target_l1 or '',
            'Client L2': result.target_l2 or '',
            'Client L3': result.target_l3 or '',
            'Matched L1': result.matched_l1 or '',
            'Matched L2': result.matched_l2 or '',
            'Matched L3': result.matched_l3 or '',
            'Confidence': round(result.confidence, 3),
            'Status': result.status or '',
            'Validation': validation_status,
            'Reasoning': result.reasoning or '',
        })
    
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    
    if request.format == "excel":
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="match_results.xlsx"'},
        )
    else:
        df.to_csv(output, index=False)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="match_results.csv"'},
        )


@app.post("/export/taxonomy")
async def export_taxonomy_tree(request: ExportTaxonomyRequest, db: Session = Depends(get_db)):
    """Export taxonomy tree to CSV or Excel."""
    service = TaxonomyService(db)
    try:
        nodes_data = await service.get_our_taxonomy(request.target_id)
        
        # Flatten tree structure
        def flatten_node(node_data, level=0, parent_l1=None, parent_l2=None):
            l1 = node_data.get("l1") or parent_l1 or ""
            l2 = node_data.get("l2") or parent_l2 or ""
            l3 = node_data.get("l3", "")
            
            rows = []
            if l3:
                rows.append({
                    'Level': level,
                    'L1': l1,
                    'L2': l2,
                    'L3': l3,
                    'Definition': node_data.get("definition", ""),
                })
            
            # Handle children if they exist
            children = node_data.get("children", [])
            for child in children:
                rows.extend(flatten_node(child, level + 1, l1, l2))
            
            return rows
        
        # Build tree structure first (similar to get_our_taxonomy endpoint)
        nodes_map = {}
        root_nodes = []
        
        for node_data in nodes_data:
            l1 = node_data.get("l1", "")
            l2 = node_data.get("l2", "")
            l3 = node_data.get("l3", "")
            
            node_dict = {
                "l1": l1 if l1 else None,
                "l2": l2 if l2 else None,
                "l3": l3,
                "definition": node_data.get("definition"),
                "children": [],
            }
            
            if l1 and l2:
                key = f"{l1}::{l2}"
                if key not in nodes_map:
                    parent = {"l1": l1, "l2": l2, "l3": "", "children": [], "definition": None}
                    nodes_map[key] = parent
                    if l1 not in nodes_map:
                        l1_node = {"l1": l1, "l2": "", "l3": "", "children": [], "definition": None}
                        nodes_map[l1] = l1_node
                        root_nodes.append(l1_node)
                    nodes_map[l1]["children"].append(parent)
                nodes_map[key]["children"].append(node_dict)
            elif l2:
                key = l2
                if key not in nodes_map:
                    parent = {"l2": l2, "l3": "", "children": [], "definition": None}
                    nodes_map[key] = parent
                    root_nodes.append(parent)
                nodes_map[key]["children"].append(node_dict)
            else:
                root_nodes.append(node_dict)
        
        # Flatten all nodes
        all_rows = []
        for root_node in root_nodes:
            all_rows.extend(flatten_node(root_node))
        
        if not all_rows:
            raise HTTPException(status_code=400, detail="No taxonomy data to export")
        
        df = pd.DataFrame(all_rows)
        output = io.BytesIO()
        
        if request.format == "excel":
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="taxonomy_{request.target_id}.xlsx"'},
            )
        else:
            df.to_csv(output, index=False)
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.read()),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="taxonomy_{request.target_id}.csv"'},
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/export/vector-status")
async def export_vector_status_data(request: ExportVectorStatusRequest):
    """Export vector status to CSV or Excel."""
    try:
        status = await check_vector_embeddings_status(request.target_id)
        
        rows = []
        for target_id, target_status in status.get("targets", {}).items():
            rows.append({
                'Target ID': target_id or '(unknown)',
                'Total Records': target_status.get('total_records', 0),
                'Categories': target_status.get('num_categories', 0),
                'Completeness %': round(target_status.get('completeness_ratio', 0) * 100, 1),
                'Ready for Matching': 'Yes' if target_status.get('ready_for_hybrid_matching') else 'No',
                'Has L1': 'Yes' if target_status.get('has_required_components', {}).get('l1') else 'No',
                'Has L2': 'Yes' if target_status.get('has_required_components', {}).get('l2') else 'No',
                'Has L3': 'Yes' if target_status.get('has_required_components', {}).get('l3') else 'No',
                'Has Full': 'Yes' if target_status.get('has_required_components', {}).get('full') else 'No',
                'Has Description': 'Yes' if target_status.get('has_required_components', {}).get('desc') else 'No',
            })
        
        if not rows:
            raise HTTPException(status_code=400, detail="No vector status data to export")
        
        df = pd.DataFrame(rows)
        output = io.BytesIO()
        
        if request.format == "excel":
            df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="vector_status.xlsx"'},
            )
        else:
            df.to_csv(output, index=False)
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.read()),
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="vector_status.csv"'},
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
