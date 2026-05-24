from fastmcp import FastMCP


mcp = FastMCP("MathServer")


@mcp.tool()
def multiply_by_two(number: float) -> float:
    """Multiply given number by 2"""
    print(" I am special tool for Vova and answer is:")
    return number * 2.0


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b"""
    if b == 0:
        return "Zero division error"
    print(" I am special tool for Vova and answer is:")
    return a / b

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=40142)
