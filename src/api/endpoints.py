"""
FastAPI接口端点
"""
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

from ..core.database import db_manager
from ..retrieval.retriever import MedicalRetriever
from ..kg_builder.graph_updater import GraphUpdater
from ..config.settings import settings

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="医疗知识图谱系统",
    description="基于Neo4j和UMLS的医疗知识图谱检索系统",
    version="2.0.0"
)

# 全局变量
retriever = None
graph_updater = None

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global retriever, graph_updater
    
    try:
        # 连接数据库
        db_manager.connect()
        logger.info("数据库连接成功")
        
        # 初始化检索器和图谱更新器
        retriever = MedicalRetriever()
        graph_updater = GraphUpdater()
        
        logger.info("API服务启动成功")
    except Exception as e:
        logger.error(f"API服务启动失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    try:
        db_manager.close()
        logger.info("API服务关闭")
    except Exception as e:
        logger.error(f"API服务关闭时出错: {e}")

# 请求模型
class QueryRequest(BaseModel):
    query: str
    max_results: Optional[int] = 20

class AddDataRequest(BaseModel):
    notepad_content: str
    hospital_number: Optional[str] = None
    merge_existing_patient: bool = True

class QueryResponse(BaseModel):
    query: str
    confidence: float
    entities: List[dict]
    relationships: List[dict]
    reasoning_chain: Optional[str]

class AddDataResponse(BaseModel):
    success: bool
    message: str
    entities_count: int
    relationships_count: int

# API端点
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "医疗知识图谱系统API",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查数据库连接
        db_manager.execute_query("RETURN 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"服务不可用: {e}")

@app.post("/query", response_model=QueryResponse)
async def query_knowledge_graph(request: QueryRequest):
    """查询知识图谱"""
    try:
        if not retriever:
            raise HTTPException(status_code=503, detail="检索器未初始化")
        
        # 执行检索
        result = retriever.retrieve(request.query)
        
        # 限制结果数量
        entities = result.entities[:request.max_results] if request.max_results else result.entities
        relationships = result.relationships[:request.max_results] if request.max_results else result.relationships
        
        # 转换为字典格式
        entities_dict = [
            {
                "id": entity.id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "properties": entity.properties,
                "namespace": entity.namespace
            }
            for entity in entities
        ]
        
        relationships_dict = [
            {
                "id": rel.id,
                "source": rel.source,
                "target": rel.target,
                "relationship_type": rel.relationship_type,
                "properties": rel.properties,
                "namespace": rel.namespace
            }
            for rel in relationships
        ]
        
        return QueryResponse(
            query=request.query,
            confidence=result.confidence,
            entities=entities_dict,
            relationships=relationships_dict,
            reasoning_chain=result.reasoning_chain
        )
        
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")

@app.post("/add_data", response_model=AddDataResponse)
async def add_new_data(request: AddDataRequest):
    """添加新数据到知识图谱"""
    try:
        if not graph_updater:
            raise HTTPException(status_code=503, detail="图谱更新器未初始化")
        
        # 添加新数据
        graph_data = graph_updater.add_new_data_from_notepad(
            request.notepad_content,
            request.hospital_number,
            request.merge_existing_patient
        )
        
        if graph_data.entities:
            return AddDataResponse(
                success=True,
                message="数据添加成功",
                entities_count=len(graph_data.entities),
                relationships_count=len(graph_data.relationships)
            )
        else:
            return AddDataResponse(
                success=False,
                message="数据添加失败",
                entities_count=0,
                relationships_count=0
            )
        
    except Exception as e:
        logger.error(f"添加数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加数据失败: {e}")

@app.get("/stats")
async def get_statistics():
    """获取系统统计信息"""
    try:
        # 获取实体统计
        entity_stats = db_manager.execute_query("""
            MATCH (e:Entity)
            RETURN e.namespace as namespace, count(e) as count
            ORDER BY namespace
        """)
        
        # 获取关系统计
        relationship_stats = db_manager.execute_query("""
            MATCH ()-[r:RELATIONSHIP]->()
            RETURN r.namespace as namespace, count(r) as count
            ORDER BY namespace
        """)
        
        return {
            "entities": {stat["namespace"]: stat["count"] for stat in entity_stats},
            "relationships": {stat["namespace"]: stat["count"] for stat in relationship_stats}
        }
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
