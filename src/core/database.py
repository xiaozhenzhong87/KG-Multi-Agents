"""
Neo4j数据库管理器
"""
from neo4j import GraphDatabase
from py2neo import Graph
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import logging

from .models import Entity, Relationship
from ..config.settings import settings
from .umls_mapping import UMLS_SEMANTIC_TYPE_MAPPING

logger = logging.getLogger(__name__)

class Neo4jManager:
    """Neo4j数据库管理器"""
    
    def __init__(self):
        self.driver = None
        self.graph = None
    
    def connect(self):
        """连接到Neo4j数据库"""
        if self.driver is None:
            self._connect()
    
    def _connect(self):
        """内部连接方法"""
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self.graph = Graph(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            logger.info("成功连接到Neo4j数据库")
        except Exception as e:
            logger.error(f"连接Neo4j数据库失败: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """获取数据库会话（上下文管理器）"""
        if self.driver is None:
            self.connect()
        
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            self.driver = None
            self.graph = None
    
    def create_indexes(self):
        """创建数据库索引"""
        try:
            with self.get_session() as session:
                # 为Entity节点的常用字段创建索引
                indexes = [
                    "CREATE INDEX entity_id_index IF NOT EXISTS FOR (n:Entity) ON (n.id)",
                    "CREATE INDEX entity_name_index IF NOT EXISTS FOR (n:Entity) ON (n.name)",
                    "CREATE INDEX entity_type_index IF NOT EXISTS FOR (n:Entity) ON (n.entity_type)",
                    "CREATE INDEX entity_namespace_index IF NOT EXISTS FOR (n:Entity) ON (n.namespace)",
                    "CREATE INDEX relationship_type_index IF NOT EXISTS FOR ()-[r:RELATIONSHIP]-() ON (r.relationship_type)",
                    "CREATE INDEX relationship_namespace_index IF NOT EXISTS FOR ()-[r:RELATIONSHIP]-() ON (r.namespace)"
                ]
                
                for index_query in indexes:
                    try:
                        session.run(index_query)
                    except Exception as e:
                        logger.warning(f"创建索引失败: {e}")
                
                logger.info("数据库索引创建完成")
        except Exception as e:
            logger.error(f"创建索引时出错: {e}")
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行Cypher查询"""
        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return []
    
    def create_entity(self, entity: Entity) -> bool:
        """创建实体节点"""
        try:
            query = """
            CREATE (n:Entity {
                id: $id,
                name: $name,
                entity_type: $entity_type,
                namespace: $namespace,
                created_at: $created_at,
                updated_at: $updated_at
            })
            """
            parameters = {
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'namespace': entity.namespace,
                'created_at': entity.created_at,
                'updated_at': entity.updated_at
            }
            self.execute_query(query, parameters)
            
            # 如果有properties，单独设置
            if entity.properties:
                for key, value in entity.properties.items():
                    if isinstance(value, (str, int, float, bool, list)):
                        set_query = f"MATCH (n:Entity {{id: $id}}) SET n.{key} = $value"
                        self.execute_query(set_query, {'id': entity.id, 'value': value})
            
            # 如果有embedding，单独设置
            if entity.embedding:
                set_query = "MATCH (n:Entity {id: $id}) SET n.embedding = $embedding"
                self.execute_query(set_query, {'id': entity.id, 'embedding': entity.embedding})
            
            return True
        except Exception as e:
            logger.error(f"创建实体失败: {e}")
            return False
    
    def create_relationship(self, relationship: Relationship) -> bool:
        """创建关系（单个关系创建，带去重逻辑）"""
        try:
            # 清理关系类型名称，确保符合Neo4j标签规范
            clean_rel_type = relationship.relationship_type.replace(' ', '_').replace('-', '_').replace(':', '_')
            if not clean_rel_type[0].isalpha():
                clean_rel_type = 'REL_' + clean_rel_type
            
            # 使用MERGE基于source-target-type去重
            query = f"""
            MATCH (a:Entity {{id: $source}})
            MATCH (b:Entity {{id: $target}})
            MERGE (a)-[r:{clean_rel_type}]->(b)
            ON CREATE SET 
                r.id = $id,
                r.namespace = $namespace,
                r.confidence = $confidence,
                r.created_at = $created_at
            ON MATCH SET
                r.confidence = COALESCE($confidence, r.confidence)
            """
            parameters = {
                'source': relationship.source,
                'target': relationship.target,
                'id': relationship.id,
                'confidence': relationship.confidence,
                'namespace': relationship.namespace,
                'created_at': relationship.created_at
            }
            self.execute_query(query, parameters)
            
            # 如果有properties，单独设置
            if relationship.properties:
                set_parts = []
                for key, value in relationship.properties.items():
                    if isinstance(value, (str, int, float, bool, list)) and value:
                        set_parts.append(f"r.{key} = ${key}")
                        parameters[key] = value
                
                if set_parts:
                    set_query = f"""
                    MATCH (a:Entity {{id: $source}})-[r:{clean_rel_type}]->(b:Entity {{id: $target}})
                    SET {', '.join(set_parts)}
                    """
                    self.execute_query(set_query, parameters)
            
            return True
        except Exception as e:
            logger.error(f"创建关系失败: {e}")
            return False
    
    def create_entities_batch(self, entities: List[Entity], batch_size: int = 10000) -> int:
        """批量创建实体节点"""
        import time
        from tqdm import tqdm
        
        total_created = 0
        total_entities = len(entities)
        start_time = time.time()
        
        logger.info(f"开始批量创建实体: 总计 {total_entities} 个实体，批次大小 {batch_size}")
        
        # 创建进度条
        with tqdm(total=total_entities, desc="创建实体", unit="实体") as pbar:
            for i in range(0, total_entities, batch_size):
                batch = entities[i:i + batch_size]
                batch_start_time = time.time()
                
                # 构建批量插入的Cypher查询 - 使用MERGE防止重复
                # 根据entity_type设置不同的节点标签
                query = """
                UNWIND $entities AS entity
                MERGE (n:Entity {id: entity.id, namespace: entity.namespace})
                ON CREATE SET 
                    n.name = entity.name,
                    n.entity_type = entity.entity_type,
                    n.created_at = entity.created_at,
                    n.updated_at = entity.updated_at,
                    n.cui = entity.cui,
                    n.definition = entity.definition,
                    n.semantic_definition = entity.semantic_definition,
                    n.embedding = entity.embedding
                ON MATCH SET
                    n.updated_at = entity.updated_at,
                    n.embedding = entity.embedding
                WITH n, entity
                CALL apoc.create.addLabels(n, [entity.label]) YIELD node
                RETURN count(node) as created
                """
                
                # 准备批量数据
                batch_data = []
                for entity in batch:
                    # 根据entity_type获取人类可读的标签名称
                    label = UMLS_SEMANTIC_TYPE_MAPPING.get(entity.entity_type, entity.entity_type)
                    
                    entity_data = {
                        'id': entity.id,
                        'name': entity.name,
                        'entity_type': entity.entity_type,
                        'namespace': entity.namespace,
                        'created_at': entity.created_at,
                        'updated_at': entity.updated_at,
                        'cui': entity.properties.get('cui', ''),
                        'definition': entity.properties.get('definition', ''),
                        'semantic_definition': entity.properties.get('semantic_definition', ''),
                        'embedding': entity.embedding,
                        'label': label
                    }
                    batch_data.append(entity_data)
                
                # 执行批量插入
                self.execute_query(query, {'entities': batch_data})
                
                total_created += len(batch)
                batch_time = time.time() - batch_start_time
                elapsed_time = time.time() - start_time
                
                # 更新进度条
                pbar.update(len(batch))
                
                # 计算速度和时间估算
                if total_created > 0:
                    avg_speed = total_created / elapsed_time
                    remaining = total_entities - total_created
                    eta_seconds = remaining / avg_speed if avg_speed > 0 else 0
                    eta_minutes = eta_seconds / 60
                    
                    # 每1000个实体或每批次记录一次详细日志
                    if total_created % 1000 == 0 or i + batch_size >= total_entities:
                        logger.info(f"进度: {total_created}/{total_entities} ({total_created/total_entities*100:.1f}%) "
                                  f"| 速度: {avg_speed:.1f} 实体/秒 | 批次耗时: {batch_time:.2f}秒 | "
                                  f"预计剩余: {eta_minutes:.1f}分钟")
        
        total_time = time.time() - start_time
        avg_speed = total_created / total_time if total_time > 0 else 0
        
        logger.info(f"实体创建完成! 总计: {total_created} 个实体, 耗时: {total_time:.2f}秒, "
                   f"平均速度: {avg_speed:.1f} 实体/秒")
        
        return total_created
    
    def create_relationships_batch(self, relationships: List[Relationship], batch_size: int = 10000) -> int:
        """批量创建关系"""
        import time
        from tqdm import tqdm
        
        total_created = 0
        total_relationships = len(relationships)
        start_time = time.time()
        
        logger.info(f"开始批量创建关系: 总计 {total_relationships} 个关系，批次大小 {batch_size}")
        
        # 创建进度条
        with tqdm(total=total_relationships, desc="创建关系", unit="关系") as pbar:
            for i in range(0, total_relationships, batch_size):
                batch = relationships[i:i + batch_size]
                batch_start_time = time.time()
                
                # 使用MERGE防止重复关系，使用具体的关系类型
                # 按关系类型分组处理，因为Neo4j需要为每种关系类型创建单独的查询
                relationships_by_type = {}
                for rel in batch:
                    rel_type = rel.relationship_type
                    if rel_type not in relationships_by_type:
                        relationships_by_type[rel_type] = []
                    relationships_by_type[rel_type].append(rel)
                
                # 使用具体的关系类型作为Neo4j关系标签，而不是统一的RELATIONSHIP
                # 这样 type(r) 将返回具体的关系类型，如 is_a, part_of 等
                # 按关系类型分组处理，为每种关系类型创建单独的查询
                for rel_type, type_relationships in relationships_by_type.items():
                    # 清理关系类型名称，确保符合Neo4j标签规范
                    clean_rel_type = rel_type.replace(' ', '_').replace('-', '_').replace(':', '_')
                    if not clean_rel_type[0].isalpha():
                        clean_rel_type = 'REL_' + clean_rel_type
                    
                    # 修改：基于source-target-type去重，而不是id
                    # MERGE条件中不包含id和namespace，这样相同的source-target-type组合只会创建一条关系
                    type_query = f"""
                    UNWIND $relationships AS rel
                    WITH rel
                    MATCH (a:Entity {{id: rel.source}})
                    MATCH (b:Entity {{id: rel.target}})
                    MERGE (a)-[r:{clean_rel_type}]->(b)
                    ON CREATE SET 
                        r.id = rel.id,
                        r.namespace = rel.namespace,
                        r.confidence = rel.confidence,
                        r.created_at = rel.created_at,
                        r.original_relation = rel.original_relation,
                        r.definition = rel.definition
                    ON MATCH SET
                        r.confidence = COALESCE(rel.confidence, r.confidence),
                        r.original_relation = COALESCE(rel.original_relation, r.original_relation),
                        r.definition = COALESCE(rel.definition, r.definition)
                    """
                    
                    # 准备该关系类型的数据
                    type_batch_data = []
                    for rel in type_relationships:
                        rel_data = {
                            'source': rel.source,
                            'target': rel.target,
                            'id': rel.id,
                            'relationship_type': rel.relationship_type,
                            'confidence': rel.confidence,
                            'namespace': rel.namespace,
                            'created_at': rel.created_at,
                            'original_relation': rel.properties.get('original_relation', ''),
                            'definition': rel.properties.get('definition', '')
                        }
                        type_batch_data.append(rel_data)
                    
                    # 执行该关系类型的查询
                    self.execute_query(type_query, {'relationships': type_batch_data})
                
                total_created += len(batch)
                batch_time = time.time() - batch_start_time
                elapsed_time = time.time() - start_time
                
                # 更新进度条
                pbar.update(len(batch))
                
                # 计算速度和时间估算
                if total_created > 0:
                    avg_speed = total_created / elapsed_time
                    remaining = total_relationships - total_created
                    eta_seconds = remaining / avg_speed if avg_speed > 0 else 0
                    eta_minutes = eta_seconds / 60
                    
                    # 每1000个关系或每批次记录一次详细日志
                    if total_created % 1000 == 0 or i + batch_size >= total_relationships:
                        logger.info(f"进度: {total_created}/{total_relationships} ({total_created/total_relationships*100:.1f}%) "
                                  f"| 速度: {avg_speed:.1f} 关系/秒 | 批次耗时: {batch_time:.2f}秒 | "
                                  f"预计剩余: {eta_minutes:.1f}分钟")
        
        total_time = time.time() - start_time
        avg_speed = total_created / total_time if total_time > 0 else 0
        
        logger.info(f"关系创建完成! 总计: {total_created} 个关系, 耗时: {total_time:.2f}秒, "
                   f"平均速度: {avg_speed:.1f} 关系/秒")
        
        return total_created
    
    def find_entities_by_type(self, entity_type: str, namespace: str = None) -> List[Entity]:
        """根据类型查找实体"""
        query = "MATCH (n:Entity) WHERE n.entity_type = $entity_type"
        parameters = {"entity_type": entity_type}
        
        if namespace:
            query += " AND n.namespace = $namespace"
            parameters["namespace"] = namespace
        
        results = self.execute_query(query, parameters)
        return [Entity(**record) for record in results]
    
    def find_entities_by_name(self, name: str, namespace: str = None) -> List[Entity]:
        """根据名称查找实体"""
        query = "MATCH (n:Entity) WHERE n.name CONTAINS $name"
        parameters = {"name": name}
        
        if namespace:
            query += " AND n.namespace = $namespace"
            parameters["namespace"] = namespace
        
        results = self.execute_query(query, parameters)
        return [Entity(**record) for record in results]
    
    def find_entities_by_id(self, entity_id: str, namespace: str = None) -> Optional[Entity]:
        """根据ID查找实体"""
        query = "MATCH (n:Entity) WHERE n.id = $entity_id"
        parameters = {"entity_id": entity_id}
        
        if namespace:
            query += " AND n.namespace = $namespace"
            parameters["namespace"] = namespace
        
        results = self.execute_query(query, parameters)
        if results:
            return Entity(**results[0])
        return None
    
    def find_relationships(self, source_id: str = None, target_id: str = None, 
                         relationship_type: str = None, namespace: str = None) -> List[Dict[str, Any]]:
        """查找关系（支持动态关系类型）"""
        params = {}
        where_clauses = []

        # 基础匹配不限定关系类型，兼容动态标签
        if source_id and target_id:
            base_match = "MATCH (a:Entity {id: $source_id}) -[r]-> (b:Entity {id: $target_id})"
            params['source_id'] = source_id
            params['target_id'] = target_id
        elif source_id:
            base_match = "MATCH (a:Entity {id: $source_id}) -[r]-> (b:Entity)"
            params['source_id'] = source_id
        elif target_id:
            base_match = "MATCH (a:Entity) -[r]-> (b:Entity {id: $target_id})"
            params['target_id'] = target_id
        else:
            base_match = "MATCH (a:Entity) -[r]-> (b:Entity)"

        # 过滤关系类型：优先属性，其次标签名
        if relationship_type:
            where_clauses.append("(r.relationship_type = $relationship_type OR type(r) = $relationship_type)")
            params['relationship_type'] = relationship_type

        if namespace:
            where_clauses.append("(r.namespace = $namespace)")
            params['namespace'] = namespace

        where_clause = ""
        if where_clauses:
            where_clause = " WHERE " + " AND ".join(where_clauses)

        query = f"{base_match}{where_clause} RETURN a, r, b"
        return self.execute_query(query, params)
    
    def update_entity(self, entity: Entity) -> bool:
        """更新实体"""
        try:
            query = """
            MATCH (n:Entity {id: $id})
            SET n.name = $name,
                n.entity_type = $entity_type,
                n.namespace = $namespace,
                n.updated_at = $updated_at
            """
            parameters = {
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'namespace': entity.namespace,
                'updated_at': entity.updated_at
            }
            self.execute_query(query, parameters)
            
            # 更新属性
            if entity.properties:
                for key, value in entity.properties.items():
                    if isinstance(value, (str, int, float, bool, list)):
                        set_query = f"MATCH (n:Entity {{id: $id}}) SET n.{key} = $value"
                        self.execute_query(set_query, {'id': entity.id, 'value': value})
            
            return True
        except Exception as e:
            logger.error(f"更新实体失败: {e}")
            return False
    
    def delete_entity(self, entity_id: str, namespace: str = None) -> bool:
        """删除实体"""
        try:
            query = "MATCH (n:Entity {id: $entity_id})"
            parameters = {"entity_id": entity_id}
            
            if namespace:
                query += " WHERE n.namespace = $namespace"
                parameters["namespace"] = namespace
            
            query += " DETACH DELETE n"
            
            self.execute_query(query, parameters)
            return True
        except Exception as e:
            logger.error(f"删除实体失败: {e}")
            return False
    
    def clear_namespace(self, namespace: str) -> bool:
        """清除指定命名空间的所有数据"""
        try:
            query = """
            MATCH (n:Entity {namespace: $namespace})
            DETACH DELETE n
            """
            self.execute_query(query, {"namespace": namespace})
            return True
        except Exception as e:
            logger.error(f"清除命名空间失败: {e}")
            return False
    
    def get_entity_count(self, namespace: str = None) -> int:
        """获取实体数量"""
        query = "MATCH (n:Entity)"
        parameters = {}
        
        if namespace:
            query += " WHERE n.namespace = $namespace"
            parameters["namespace"] = namespace
        
        query += " RETURN count(n) as count"
        
        results = self.execute_query(query, parameters)
        return results[0]["count"] if results else 0
    
    def get_relationship_count(self, namespace: str = None) -> int:
        """获取关系数量（兼容动态关系类型）"""
        query = "MATCH ()-[r]->()"
        parameters = {}

        if namespace:
            query += " WHERE r.namespace = $namespace"
            parameters["namespace"] = namespace

        query += " RETURN count(r) as count"

        results = self.execute_query(query, parameters)
        return results[0]["count"] if results else 0
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            with self.get_session() as session:
                result = session.run("RETURN 1 as test")
                return result.single()["test"] == 1
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return False


# 全局数据库管理器实例（延迟初始化）
db_manager = Neo4jManager()

def get_db_manager() -> Neo4jManager:
    """获取数据库管理器实例（单例模式）"""
    return db_manager