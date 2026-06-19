from pathlib import Path

from backend.app.parsers.base import SourceFile
from backend.app.parsers.mybatis_parser import MyBatisParser


def test_mybatis_parser_extracts_sql_metadata():
    path = Path("backend/examples/bank_sample/mapper/CustomerMapper.xml")
    docs = MyBatisParser().parse(SourceFile(path=path, language="xml", text=path.read_text(encoding="utf-8")))
    select = next(doc for doc in docs if doc.sql_id == "CustomerMapper.selectCustomer")
    update = next(doc for doc in docs if doc.sql_id == "CustomerMapper.updateCustomer")

    assert select.metadata["crud"] == "SELECT"
    assert "TB_CUSTOMER" in select.tables
    assert "customerNo" in select.metadata["parameters"]
    assert any("USE_YN" in rule for rule in select.business_rules)
    assert update.metadata["crud"] == "UPDATE"
    assert "STATUS" in update.columns


def test_mybatis_parser_ignores_xml_comments():
    text = """
    <mapper namespace="CommentMapper">
      <!-- comment nodes should not be parsed as SQL tags -->
      <select id="findOne" parameterType="map">
        SELECT * FROM TB_SAMPLE WHERE ID = #{id}
      </select>
    </mapper>
    """

    docs = MyBatisParser().parse(
        SourceFile(path=Path("CommentMapper.xml"), language="xml", text=text)
    )

    assert [doc.sql_id for doc in docs] == ["CommentMapper.findOne"]
